import copy
import unittest
from unittest.mock import patch

from update_publications import (authors, build_paper, date_string, find_match,
                                 merge_candidates, parse_orcid, parse_profile, synchronize)


CONFIG = {'scholar_id': 'profile', 'orcid_id': '0000-0002-3429-919X', 'author_names': ['Peng Jia']}
TODAY = '2026-11-16'
CANDIDATE = {'title': 'A new paper', 'doi': '10.1234/new', 'source': 'orcid',
             'source_url': 'https://pub.orcid.org/v3.0/0000-0002-3429-919X/work/123'}
METADATA = {'title': 'A new paper', 'doi': '10.1234/new', 'date': '2026-11',
            'authors': [{'name': 'Peng Jia', 'is_self': True}, {'name': 'Kai Ye', 'is_self': False}],
            'journal': 'Example Journal', 'volume': '6', 'issue': '11', 'pages': '123',
            'publisher_url': 'https://doi.org/10.1234/new', 'type': 'article',
            'metadata_source': 'https://api.crossref.org/works/10.1234%2Fnew'}


def profile(key='profile:new', more=False):
    return (f'<table><tr class="gsc_a_tr"><td><a class="gsc_a_at" href="/citations?citation_for_view={key}">'
            'A <i>new</i> paper</a></td><td><a class="gsc_a_ac">12</a></td></tr></table>'
            f'<button id="gsc_bpf_more" {"" if more else "disabled"}>More</button>').encode()


class PublicationTests(unittest.TestCase):
    def test_orcid_group_has_all_self_dois_and_prefers_published(self):
        def work(kind, doi, code):
            return {'type': kind, 'put-code': code, 'title': {'title': {'value': 'A new paper'}},
                    'external-ids': {'external-id': [
                        {'external-id-type': 'doi', 'external-id-value': doi, 'external-id-relationship': 'self'},
                        {'external-id-type': 'doi', 'external-id-value': '10.1234/parent', 'external-id-relationship': 'part-of'}]}}
        candidates = parse_orcid({'group': [{'work-summary': [work('preprint', '10.1101/preprint', 1),
                                                             work('journal-article', 'https://doi.org/10.1234/NEW', 2)]}]}, CONFIG)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['doi'], '10.1234/new')
        self.assertEqual(set(candidates[0]['doi_aliases']), {'10.1234/new', '10.1101/preprint'})
        self.assertTrue(candidates[0]['source_url'].endswith('/2'))

    def test_orcid_error_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_orcid({'error': 'rate limited'}, CONFIG)
        self.assertEqual(parse_orcid({'group': []}, CONFIG), [])

    def test_profile_parses_full_title_counts_and_pagination(self):
        candidates, more = parse_profile(profile(more=True), CONFIG)
        self.assertTrue(more)
        self.assertEqual(candidates[0]['title'], 'A new paper')
        self.assertEqual(candidates[0]['citations'], 12)
        self.assertFalse(parse_profile(profile(), CONFIG)[1])

    def test_profile_rejects_block_and_wrong_identity(self):
        for raw in (b'<html>CAPTCHA</html>', profile(key='someone-else:new')):
            with self.assertRaises(ValueError):
                parse_profile(raw, CONFIG)

    def test_deduplicate_doi_and_normalized_title(self):
        paper = {'title': 'A <sup>new</sup> paper.', 'doi': 'https://doi.org/10.1234/NEW'}
        self.assertIs(find_match([paper], CANDIDATE), paper)
        self.assertIs(find_match([paper], {'title': 'A new paper', 'doi': '10.1101/preprint'}), paper)
        self.assertIsNone(find_match([paper], {'title': 'A different paper'}))

    def test_author_identity_requires_full_name_or_orcid(self):
        with self.assertRaises(ValueError):
            authors([('P Jia', '')], CONFIG)
        with self.assertRaises(ValueError):
            authors([('Peng Jia', 'https://orcid.org/0000-0000-0000-0000')], CONFIG)
        with self.assertRaises(ValueError):
            authors([('Peng Jia', ''), ('et al.', '')], CONFIG)
        self.assertTrue(authors([('Jia, Peng', 'https://orcid.org/' + CONFIG['orcid_id'])], CONFIG)[0]['is_self'])

    def test_partial_dates_preserve_precision(self):
        self.assertEqual(date_string([2026]), '2026')
        self.assertEqual(date_string([2026, 11]), '2026-11')
        with self.assertRaises(ValueError):
            date_string([2026, 2, 30])

    @patch('update_publications.europepmc_metadata', return_value={'pmid': '12345', 'date': '2026-11-03'})
    @patch('update_publications.crossref_metadata', return_value=METADATA)
    def test_import_is_idempotent_and_keeps_editorial_choices(self, crossref, epmc):
        papers, warnings = [], []
        added = merge_candidates(papers, [CANDIDATE], None, CONFIG, TODAY, warnings)
        self.assertEqual(added, ['A new paper'])
        self.assertEqual(papers[0]['date'], '2026-11-03')
        self.assertEqual(papers[0]['pmid'], '12345')
        self.assertFalse(papers[0]['selected'])
        papers[0].update(selected=True, role='corresponding', role_evidence='Manual confirmation', code_url='https://example.org/code')
        original = copy.deepcopy(papers)
        self.assertEqual(merge_candidates(papers, [CANDIDATE], None, CONFIG, TODAY, warnings), [])
        self.assertEqual(papers, original)
        self.assertEqual(crossref.call_count, 1)

    @patch('update_publications.crossref_metadata', return_value={**METADATA, 'title': 'Unrelated paper'})
    @patch('update_publications.europepmc_metadata', return_value={})
    def test_conflicting_metadata_is_deferred(self, epmc, crossref):
        papers, warnings = [], []
        self.assertEqual(merge_candidates(papers, [CANDIDATE], None, CONFIG, TODAY, warnings), [])
        self.assertEqual(papers, [])
        self.assertIn('titles do not agree', warnings[0])

    @patch('update_publications.crossref_metadata', side_effect=RuntimeError('offline'))
    @patch('update_publications.source_metadata', return_value=METADATA)
    @patch('update_publications.europepmc_metadata', side_effect=RuntimeError('offline'))
    def test_orcid_full_metadata_survives_enrichment_failure(self, epmc, source, crossref):
        warnings = []
        paper = build_paper(CANDIDATE, None, CONFIG, TODAY, warnings)
        self.assertEqual(paper['title'], CANDIDATE['title'])
        self.assertEqual(len(warnings), 2)

    def test_scholar_attaches_to_orcid_paper_without_duplicate(self):
        papers = [{'title': 'A new paper', 'doi': '10.1234/new', 'selected': True}]
        candidate = parse_profile(profile(), CONFIG)[0][0]
        self.assertEqual(merge_candidates(papers, [candidate], None, CONFIG, TODAY, []), [])
        self.assertEqual(papers[0]['citations'], 12)
        self.assertTrue(papers[0]['selected'])
        original = copy.deepcopy(papers)
        candidate['scholar_url'] = candidate['scholar_url'].replace('profile:new', 'profile:preprint')
        candidate['citations'] = 100
        merge_candidates(papers, [candidate], None, CONFIG, TODAY, [])
        self.assertEqual(papers, original)

    @patch('update_publications.update', return_value=(0, []))
    @patch('update_publications.request_bytes', side_effect=RuntimeError('Scholar blocked'))
    @patch('update_publications.read_json', return_value={'group': []})
    def test_scholar_failure_does_not_discard_orcid_success(self, read, request, citations):
        papers = [{'title': 'Old paper', 'citations': 99, 'citations_checked': '2026-10-01'}]
        original = copy.deepcopy(papers)
        result = synchronize(papers, None, CONFIG, TODAY)
        self.assertEqual(result['sources'], ['ORCID: 0 work groups'])
        self.assertEqual(papers, original)
        self.assertIn('Scholar blocked', result['warnings'][0])

    @patch('update_publications.update', return_value=(0, []))
    @patch('update_publications.request_bytes', side_effect=[profile(more=True), profile('profile:second')])
    @patch('update_publications.read_json', side_effect=RuntimeError('ORCID offline'))
    def test_orcid_failure_does_not_block_scholar_pagination(self, read, request, citations):
        papers = [{'title': 'A new paper', 'scholar_url': None}]
        result = synchronize(papers, None, CONFIG, TODAY)
        self.assertEqual(result['sources'], ['Google Scholar: 2 records'])
        self.assertEqual(papers[0]['citations'], 12)
        self.assertEqual(request.call_count, 2)
        self.assertIn('cstart=100', request.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
