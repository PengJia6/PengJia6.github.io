import copy
import unittest
from unittest.mock import patch

from update_citations import parse_pubmed, parse_scholar, update


class CitationTests(unittest.TestCase):
    def test_pubmed_deduplicates_citing_ids(self):
        raw = b'<eLinkResult><LinkSet><IdList><Id>123</Id></IdList><LinkSetDb><LinkName>pubmed_pubmed_citedin</LinkName><Link><Id>456</Id></Link><Link><Id>456</Id></Link></LinkSetDb></LinkSet></eLinkResult>'
        self.assertEqual(parse_pubmed(raw, '123'), 1)

    def test_pubmed_zero_requires_matching_record(self):
        self.assertEqual(parse_pubmed(b'<eLinkResult><LinkSet><IdList><Id>123</Id></IdList></LinkSet></eLinkResult>', '123'), 0)
        for raw in [b'<eLinkResult/>', b'<eLinkResult><ERROR>Rate limited</ERROR></eLinkResult>']:
            with self.assertRaises(ValueError):
                parse_pubmed(raw, '123')

    def test_scholar_distinguishes_blank_and_count(self):
        raw = b'<table><tr class="gsc_a_tr"><td><a class="gsc_a_at" href="/citations?citation_for_view=user:paper">Title</a></td><td><a class="gsc_a_ac">12</a></td></tr><tr class="gsc_a_tr"><td><a class="gsc_a_at" href="/citations?citation_for_view=user:new">New</a></td><td><a class="gsc_a_ac"></a></td></tr></table>'
        self.assertEqual(parse_scholar(raw), {'user:paper': 12, 'user:new': None})

    def test_blocked_scholar_is_not_zero(self):
        with self.assertRaises(ValueError):
            parse_scholar(b'<html>Please complete the CAPTCHA</html>')

    def test_failure_preserves_old_counts_and_dates(self):
        papers = [{'id': 'paper', 'pmid': '123', 'citations': 9,
                   'citations_checked': '2026-10-01', 'pubmed_citations': 4,
                   'pubmed_citations_checked': '2026-10-01'}]
        original = copy.deepcopy(papers)
        with patch('update_citations.request_bytes', side_effect=RuntimeError('offline')), patch('update_citations.time.sleep'):
            succeeded, warnings = update(papers, None, '2026-10-22', ['scholar', 'pubmed'])
        self.assertEqual(succeeded, 0)
        self.assertEqual(len(warnings), 2)
        self.assertEqual(papers, original)


if __name__ == '__main__':
    unittest.main()
