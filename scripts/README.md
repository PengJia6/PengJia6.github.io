# Publication discovery and citation snapshots

`update_publications.py` checks the Google Scholar and ORCID profiles in
`_data/publication_sources.json`, adds new papers, and refreshes citation counts.
Both languages use the same `_data/publications.json` bibliography.

- ORCID public work groups and Google Scholar profile pages are the discovery sources.
  Scholar pagination is followed, up to 1,000 records. ORCID is queried independently
  so a blocked Scholar request cannot prevent ORCID updates.
- Exact DOI matches (including self DOI aliases grouped by ORCID), Scholar record
  IDs, then normalized exact titles prevent duplicates. Preprint and published
  records with the same title do not create a second entry. Existing bibliography,
  selected papers, authorship annotations, and code links are never overwritten or
  removed. Updates to an existing paper's bibliographic details remain manual.
- Crossref DOI metadata and Europe PMC exact DOI/title matches supply full authors,
  journal details, dates and PMID. Source-detail metadata is the fallback. Only
  papers with a full author list containing the configured author, a valid date,
  and a venue are added; incomplete or conflicting records are logged and retried
  on the next run. Discovery and metadata source URLs are saved with each new entry.
- New papers appear in the full Publications list with `selected: false`.
  First authorship follows the full author order; co-first/corresponding authorship
  and selection for the homepage remain manual. Missing DOI links are hidden.
  Partial dates retain their source precision. No citation count is invented.
- A failed source leaves its existing values intact. Partial failures and deferred
  records are visible in the Actions summary; complete source failure fails the job.

The **Update publications and citations** workflow runs every Monday at 02:17 UTC
(10:17 Asia/Shanghai), and can also be run from the Actions tab. GitHub may delay
scheduled runs. It commits only `_data/publications.json` and explicitly requests
a Pages rebuild. New-paper discovery and citation refresh use this same schedule.

Run locally with Python 3.10 or later (the workflow uses 3.12):

```sh
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/update_publications.py --dry-run
python scripts/update_publications.py
```

`--dry-run` performs the same queries and reports discoveries without changing files.
No API keys are currently needed for these public endpoints. Access restrictions
are logged as source failures; they are not bypassed.

## Citation-only command

`update_citations.py` refreshes the existing paper records without changing the bibliography.

- PubMed counts use NCBI's `pubmed_pubmed_citedin` links. This is a source-specific, potentially incomplete citing-article count.
- Google Scholar counts come from the public profile, matched by `citation_for_view` IDs. The script requests the profile once per run. If Scholar rate-limits or blocks access, the previous values and dates remain intact, and the workflow summary reports the problem. No CAPTCHA solving or access-limit bypass is attempted.
- An empty count on a successfully parsed Scholar record remains `null`, distinct from a verified NCBI count of zero.
- A successful query updates only that source's timestamp, using Asia/Shanghai dates.

For a citation-only refresh:

```sh
python -m unittest discover -s scripts -p test_update_citations.py
python scripts/update_citations.py
```

Windows environments without an IANA timezone database need the `tzdata` package. An optional `--proxy` argument can be used locally; proxy settings are never saved in the repository. Python scripts and this documentation are excluded from the generated site.
