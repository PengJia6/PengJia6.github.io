"""Refresh source-specific citation snapshots; preserve old values on failed requests."""
import argparse
from datetime import datetime
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo


class ScholarRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = {}
        self.current = None
        self.counting = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'tr' and 'gsc_a_tr' in classes:
            self.current = {'key': None, 'count': '', 'count_seen': False}
        if self.current is None:
            return
        if tag == 'a' and 'gsc_a_at' in classes:
            query = parse_qs(urlparse(attrs.get('href', '')).query)
            self.current['key'] = query.get('citation_for_view', [None])[0]
        if tag == 'a' and 'gsc_a_ac' in classes:
            self.counting = True
            self.current['count_seen'] = True

    def handle_data(self, data):
        if self.current is not None and self.counting:
            self.current['count'] += data

    def handle_endtag(self, tag):
        if tag == 'a':
            self.counting = False
        if tag == 'tr' and self.current is not None:
            row = self.current
            if row['key'] and row['count_seen']:
                count = row['count'].strip().replace(',', '')
                if count and not count.isdigit():
                    raise ValueError('Unexpected Scholar citation count')
                self.rows[row['key']] = int(count) if count else None
            self.current = None


def parse_scholar(raw):
    parser = ScholarRows()
    parser.feed(raw.decode('utf-8', errors='replace'))
    if not parser.rows:
        raise ValueError('No Scholar article rows; blocked or unexpected response')
    return parser.rows


def parse_pubmed(raw, pmid):
    root = ET.fromstring(raw)
    if root.tag != 'eLinkResult' or root.find('.//ERROR') is not None:
        raise ValueError('Unexpected NCBI response or API error')
    source = next((s for s in root.findall('LinkSet')
                   if s.findtext('IdList/Id') == str(pmid)), None)
    if source is None:
        raise ValueError('NCBI response does not match the requested PMID')
    ids = {node.text for db in source.findall('LinkSetDb')
           if db.findtext('LinkName') == 'pubmed_pubmed_citedin'
           for node in db.findall('Link/Id')}
    return len(ids)


def request_bytes(opener, url):
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'PengJiaHomepage-CitationUpdater/1.0'})
            with opener.open(request, timeout=30) as response:
                raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError('Response exceeds size limit')
            return raw
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def update(papers, opener, today, sources):
    succeeded = 0
    warnings = []
    if 'scholar' in sources:
        url = ('https://scholar.google.com/citations?user=KSYdspwAAAAJ'
               '&hl=en&cstart=0&pagesize=100')
        try:
            rows = parse_scholar(request_bytes(opener, url))
            for paper in papers:
                key = parse_qs(urlparse(paper['scholar_url']).query)['citation_for_view'][0]
                if key not in rows:
                    warnings.append('Scholar record missing: ' + paper['id'])
                    continue
                paper['citations'] = rows[key]
                paper['citations_checked'] = today
                succeeded += 1
        except Exception as error:
            warnings.append('Scholar unchanged: ' + str(error))
    if 'pubmed' in sources:
        for paper in papers:
            if not paper.get('pmid'):
                continue
            pmid = paper['pmid']
            url = ('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi'
                   '?dbfrom=pubmed&db=pubmed&linkname=pubmed_pubmed_citedin&id=' + pmid)
            try:
                count = parse_pubmed(request_bytes(opener, url), pmid)
                paper.update(pubmed_citations=count, pubmed_citations_status='ok',
                             pubmed_citations_checked=today, pubmed_citations_source=url)
                succeeded += 1
            except Exception as error:
                warnings.append('PubMed unchanged for ' + paper['id'] + ': ' + str(error))
            time.sleep(0.4)  # Stay below the unauthenticated NCBI request rate.
    return succeeded, warnings


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--data', type=Path, default=Path('_data/publications.json'))
    cli.add_argument('--sources', nargs='+', choices=['scholar', 'pubmed'],
                     default=['scholar', 'pubmed'])
    cli.add_argument('--proxy', help='Optional local HTTP(S) proxy; never stored in the repository')
    args = cli.parse_args()
    opener = build_opener(ProxyHandler({'https': args.proxy, 'http': args.proxy})) if args.proxy else build_opener()
    papers = json.loads(args.data.read_text(encoding='utf-8'))
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    succeeded, warnings = update(papers, opener, today, args.sources)
    report = f'Updated {succeeded} source records on {today}.\n'
    for warning in warnings:
        print('WARNING: ' + warning)
        report += '- ' + warning + '\n'
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
            summary.write(report)
    if not succeeded:
        raise SystemExit('No source could be refreshed; existing snapshots preserved')
    temporary = args.data.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(papers, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.data)


if __name__ == '__main__':
    main()
