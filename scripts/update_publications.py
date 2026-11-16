"""Discover papers on the configured profiles, then refresh citation snapshots.

Only exact DOI/profile-ID or normalized-title matches are merged. Existing
editorial fields are retained; new entries are never selected automatically.
"""
import argparse
from copy import deepcopy
from datetime import date, datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse
from urllib.request import ProxyHandler, build_opener
from zoneinfo import ZoneInfo

from update_citations import parse_scholar, request_bytes, update


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def find(self, attr, value):
        found = [self] if value in self.attrs.get(attr, '').split() else []
        for child in self.children:
            if isinstance(child, Node):
                found.extend(child.find(attr, value))
        return found


class Document(HTMLParser):
    def __init__(self, raw):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]
        self.feed(raw.decode('utf-8', errors='replace'))

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]+>', '', value or '')).split())


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', clean(value)).casefold() if c.isalnum())


def doi_value(value):
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value or '', flags=re.I).strip().lower()
    return value if re.fullmatch(r'10\.\d{4,9}/\S+', value) else ''


def scholar_key(url):
    return parse_qs(urlparse(url or '').query).get('citation_for_view', [''])[0]


def read_json(opener, url):
    return json.loads(request_bytes(opener, url, {'Accept': 'application/json'}))


def parse_orcid(payload, config):
    if not isinstance(payload.get('group'), list):
        raise ValueError('ORCID response has no work groups')
    candidates = []
    for group in payload['group']:
        works = [w for w in group.get('work-summary', []) if w.get('type') in
                 {'journal-article', 'conference-paper', 'preprint', 'review'}]
        if not works:
            continue
        # Prefer the journal record when ORCID groups preprint and published versions.
        works.sort(key=lambda w: (w['type'] == 'preprint', -int(w.get('display-index', 0))))
        work = works[0]
        dois = list(dict.fromkeys(doi_value(i.get('external-id-value')) for w in works
                    for i in (w.get('external-ids') or {}).get('external-id', [])
                    if i.get('external-id-type') == 'doi' and i.get('external-id-relationship') == 'self'))
        dois = [d for d in dois if d]
        if work['type'] != 'preprint':
            dois.sort(key=lambda d: d.startswith(('10.1101/', '10.21203/')))
        candidates.append({'title': clean(work['title']['title']['value']),
                           'doi': dois[0] if dois else '', 'doi_aliases': dois,
                           'type': 'preprint' if work['type'] == 'preprint' else 'article',
                           'source_url': f"https://pub.orcid.org/v3.0/{config['orcid_id']}/work/{work['put-code']}",
                           'source': 'orcid'})
    return candidates


def parse_profile(raw, config):
    counts = parse_scholar(raw)  # Reject blocks/changed markup, never interpret as an empty profile.
    document = Document(raw).root
    candidates = []
    for row in document.find('class', 'gsc_a_tr'):
        links = row.find('class', 'gsc_a_at')
        if not links:
            continue
        link = links[0]
        url = urljoin('https://scholar.google.com', link.attrs.get('href', ''))
        key = scholar_key(url)
        if not key.startswith(config['scholar_id'] + ':') or key not in counts:
            raise ValueError('Scholar row does not belong to the configured profile')
        candidates.append({'title': clean(link.text()), 'scholar_url': url,
                           'source_url': url, 'source': 'scholar', 'citations': counts[key]})
    more = document.find('id', 'gsc_bpf_more')
    return candidates, bool(more and 'disabled' not in more[0].attrs)


def find_match(papers, candidate):
    dois = {doi_value(candidate.get('doi')), *candidate.get('doi_aliases', [])} - {''}
    key = scholar_key(candidate.get('scholar_url'))
    for paper in papers:
        if dois & ({doi_value(paper.get('doi'))} | set(paper.get('doi_aliases', []))) - {''}:
            return paper
        if key and key == scholar_key(paper.get('scholar_url')):
            return paper
    title = normalized(candidate['title'])
    return next((p for p in papers if title and normalized(p['title']) == title), None)


def authors(names, config):
    result = []
    for name, orcid in names:
        name = clean(name)
        if not name or '…' in name or '...' in name or re.search(r'\bet al\b', name, re.I):
            raise ValueError('Incomplete author list')
        own = (orcid.rstrip('/').endswith('/' + config['orcid_id']) or orcid == config['orcid_id']) if orcid else normalized(name) in {normalized(n) for n in config['author_names']}
        result.append({'name': name, 'is_self': own})
    if sum(a['is_self'] for a in result) != 1:
        raise ValueError('Author identity could not be verified in the full author list')
    return result


def date_string(parts):
    parts = [int(p) for p in parts if p is not None]
    if not 1 <= len(parts) <= 3:
        raise ValueError('Missing publication date')
    date(*(parts + [1] * (3 - len(parts))))  # Validate without fabricating missing precision.
    return '-'.join(f'{p:04d}' if i == 0 else f'{p:02d}' for i, p in enumerate(parts))


def source_metadata(candidate, opener, config):
    if candidate['source'] == 'orcid':
        work = read_json(opener, candidate['source_url'])
        names = [(c.get('credit-name', {}).get('value', ''),
                  (c.get('contributor-orcid') or {}).get('uri', ''))
                 for c in (work.get('contributors') or {}).get('contributor', [])
                 if (c.get('contributor-attributes') or {}).get('contributor-role') in (None, 'author')]
        parts = [(work.get('publication-date') or {}).get(k) for k in ('year', 'month', 'day')]
        return dict(authors=authors(names, config), date=date_string([p['value'] for p in parts if p]),
                    journal=clean((work.get('journal-title') or {}).get('value')), doi=candidate.get('doi', ''),
                    publisher_url=(work.get('url') or {}).get('value', candidate['source_url']))
    root = Document(request_bytes(opener, candidate['source_url'])).root
    labels, values = root.find('class', 'gsc_oci_field'), root.find('class', 'gsc_oci_value')
    fields = {clean(k.text()): clean(v.text()) for k, v in zip(labels, values)}
    links = root.find('class', 'gsc_oci_title_link')
    link = links[0].attrs.get('href', '') if links else ''
    doi_match = re.search(r'10\.\d{4,9}/[^?#\s]+', link)
    return dict(authors=authors([(n.strip(), '') for n in fields.get('Authors', '').split(',')], config),
                date=date_string(fields.get('Publication date', '').split('/')),
                journal=fields.get('Journal') or fields.get('Conference') or fields.get('Source', ''),
                volume=fields.get('Volume', ''), issue=fields.get('Issue', ''), pages=fields.get('Pages', ''),
                doi=doi_value(doi_match[0]) if doi_match else '', publisher_url=link or candidate['source_url'])


def crossref_metadata(doi, opener, config):
    url = 'https://api.crossref.org/works/' + quote(doi, safe='')
    work = read_json(opener, url)['message']
    if doi_value(work.get('DOI')) != doi:
        raise ValueError('Crossref DOI mismatch')
    if work.get('type') not in {'journal-article', 'proceedings-article', 'posted-content'}:
        raise ValueError('Crossref record is not a paper')
    parts = (work.get('published-online') or work.get('published') or work.get('issued') or {})
    return dict(title=clean(work['title'][0]), doi=doi,
                authors=authors([(' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name', ''), a.get('ORCID', '')) for a in work.get('author', [])], config),
                date=date_string(parts.get('date-parts', [[]])[0]),
                journal=clean((work.get('container-title') or [''])[0]),
                volume=work.get('volume', ''), issue=work.get('issue', ''),
                pages=work.get('page') or work.get('article-number', ''),
                publisher_url='https://doi.org/' + doi,
                type='preprint' if work['type'] == 'posted-content' else 'article', metadata_source=url)


def europepmc_metadata(candidate, opener, config):
    doi = candidate.get('doi')
    query = 'DOI:"' + doi + '"' if doi else 'TITLE:"' + candidate['title'].replace('"', '') + '"'
    url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urlencode({'query': query, 'format': 'json', 'resultType': 'core'})
    for work in read_json(opener, url).get('resultList', {}).get('result', []):
        if doi and doi_value(work.get('doi')) != doi:
            continue
        if not doi and normalized(work['title']) != normalized(candidate['title']):
            continue
        journal = work.get('journalInfo') or {}
        names = [(' '.join(filter(None, [a.get('firstName'), a.get('lastName')])) or a.get('fullName', ''),
                  (a.get('authorId') or {}).get('value', '') if (a.get('authorId') or {}).get('type') == 'ORCID' else '')
                 for a in work.get('authorList', {}).get('author', [])]
        return dict(title=clean(work['title']).rstrip('.'), authors=authors(names, config),
                    doi=doi_value(work.get('doi')), date=date_string(work['firstPublicationDate'].split('-')),
                    year=int(work['pubYear']), journal=clean((journal.get('journal') or {}).get('title')),
                    volume=journal.get('volume', ''), issue=journal.get('issue', ''), pages=work.get('pageInfo', ''),
                    pmid=work['id'] if work.get('source') == 'MED' else None, metadata_source=url)
    return {}


def build_paper(candidate, opener, config, today, warnings):
    metadata = {}
    if candidate.get('doi'):
        try:
            metadata = crossref_metadata(candidate['doi'], opener, config)
        except Exception as error:
            warnings.append(f"Crossref metadata unavailable for {candidate['title']}: {error}")
    if not metadata:
        metadata = source_metadata(candidate, opener, config)
    try:
        extra = europepmc_metadata({**candidate, **metadata}, opener, config)
        for field, value in extra.items():
            if value and (not metadata.get(field) or field == 'pmid' or
                          (field == 'date' and len(value) > len(metadata.get(field, '')))):
                metadata[field] = value
    except Exception as error:
        warnings.append(f"Europe PMC metadata unavailable for {candidate['title']}: {error}")
    if normalized(metadata.get('title', candidate['title'])) != normalized(candidate['title']):
        raise ValueError('Source and DOI metadata titles do not agree')
    doi = doi_value(metadata.get('doi'))
    if not metadata.get('authors') or not metadata.get('date') or not metadata.get('journal'):
        raise ValueError('Missing authors, date, or publication venue; deferred until a later run')
    link = metadata.get('publisher_url') or ('https://doi.org/' + doi if doi else candidate['source_url'])
    if urlparse(link).scheme not in {'http', 'https'}:
        raise ValueError('Invalid article URL')
    paper = dict(id='auto-' + hashlib.sha256((doi or candidate['source_url']).encode()).hexdigest()[:16],
                 title=candidate['title'], authors=metadata['authors'], date=metadata['date'],
                 year=int(metadata['date'][:4]), journal=metadata['journal'],
                 volume=metadata.get('volume', ''), issue=metadata.get('issue', ''), pages=metadata.get('pages', ''),
                 doi=doi, publisher_url=link, pmid=metadata.get('pmid'),
                 type=metadata.get('type', candidate.get('type', 'article')), role='contributor', selected=False,
                 role_evidence='', role_source='', scholar_url=candidate.get('scholar_url'),
                 citations=None, citations_checked=None, metadata_source=metadata.get('metadata_source', candidate['source_url']),
                 discovery_source=candidate['source_url'], discovered_on=today)
    if candidate.get('doi_aliases'):
        paper['doi_aliases'] = candidate['doi_aliases']
    if paper['authors'][0]['is_self']:
        paper.update(role='first', role_evidence='First in the source author list.', role_source=paper['metadata_source'])
    return paper


def merge_candidates(papers, candidates, opener, config, today, warnings):
    added = []
    for candidate in candidates:
        try:
            paper = find_match(papers, candidate)
            if paper is None:
                paper = build_paper(candidate, opener, config, today, warnings)
                match = find_match(papers, paper)
                if match is not None:
                    paper = match
                else:
                    papers.append(paper)
                    added.append(paper['title'])
            if candidate['source'] == 'scholar':
                # A second version must not overwrite the curated Scholar count/link.
                if not paper.get('scholar_url'):
                    paper['scholar_url'] = candidate['scholar_url']
                if scholar_key(paper['scholar_url']) == scholar_key(candidate['scholar_url']):
                    paper.update(citations=candidate['citations'], citations_checked=today)
        except Exception as error:
            warnings.append(f"Deferred {candidate['title']}: {error}")
    return added


def synchronize(papers, opener, config, today):
    warnings, added, fetched = [], [], []
    try:
        candidates = parse_orcid(read_json(opener, f"https://pub.orcid.org/v3.0/{config['orcid_id']}/works"), config)
        added.extend(merge_candidates(papers, candidates, opener, config, today, warnings))
        fetched.append(f'ORCID: {len(candidates)} work groups')
    except Exception as error:
        warnings.append('ORCID unavailable; existing entries preserved: ' + str(error))
    try:
        seen = set()
        for start in range(0, 1000, 100):
            url = 'https://scholar.google.com/citations?' + urlencode({'user': config['scholar_id'], 'hl': 'en', 'cstart': start, 'pagesize': 100})
            candidates, more = parse_profile(request_bytes(opener, url), config)
            keys = {scholar_key(c['scholar_url']) for c in candidates}
            if keys & seen:
                raise ValueError('Repeated Scholar page')
            seen.update(keys)
            added.extend(merge_candidates(papers, candidates, opener, config, today, warnings))
            if not more:
                break
        else:
            warnings.append('Scholar profile exceeds the 1000-record safety limit')
        fetched.append(f'Google Scholar: {len(seen)} records')
    except Exception as error:
        warnings.append('Google Scholar incomplete/unavailable; unqueried values preserved: ' + str(error))
    succeeded, citation_warnings = update(papers, opener, today, ['pubmed'])
    warnings.extend(citation_warnings)
    return {'sources': fetched, 'added': added, 'pubmed_records': succeeded, 'warnings': warnings}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--data', type=Path, default=Path('_data/publications.json'))
    cli.add_argument('--config', type=Path, default=Path('_data/publication_sources.json'))
    cli.add_argument('--proxy', help='Optional local proxy; never saved')
    cli.add_argument('--dry-run', action='store_true', help='Query and report without writing data')
    args = cli.parse_args()
    opener = build_opener(ProxyHandler({'https': args.proxy, 'http': args.proxy})) if args.proxy else build_opener()
    papers = json.loads(args.data.read_text(encoding='utf-8'))
    original = deepcopy(papers)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    result = synchronize(papers, opener, config, today)
    report = f"Publication sync on {today}: {len(result['added'])} added; {result['pubmed_records']} PubMed counts refreshed.\n"
    report += '\n'.join(result['sources'] + ['Added: ' + t for t in result['added']] + ['WARNING: ' + w for w in result['warnings']]) + '\n'
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
            summary.write(report)
    if not result['sources'] and not result['pubmed_records']:
        raise SystemExit('No source could be refreshed; existing data preserved')
    if papers != original and not args.dry_run:
        temporary = args.data.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(args.data)


if __name__ == '__main__':
    main()
