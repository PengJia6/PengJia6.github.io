# Citation snapshots

`update_citations.py` refreshes the existing paper records without changing the bibliography.

- PubMed counts use NCBI's `pubmed_pubmed_citedin` links. This is a source-specific, potentially incomplete citing-article count.
- Google Scholar counts come from the public profile, matched by `citation_for_view` IDs. The script requests the profile once per run. If Scholar rate-limits or blocks access, the previous values and dates remain intact, and the workflow summary reports the problem. No CAPTCHA solving or access-limit bypass is attempted.
- An empty count on a successfully parsed Scholar record remains `null`, distinct from a verified NCBI count of zero.
- A successful query updates only that source's timestamp, using Asia/Shanghai dates.

The `Update publication citations` workflow runs every Monday at 02:17 UTC (10:17 Asia/Shanghai), and can also be run from the Actions tab. GitHub may delay scheduled runs. It commits only `_data/publications.json` and explicitly requests a Pages rebuild, because pushes made by `GITHUB_TOKEN` do not trigger the normal Pages build.

Run locally with Python 3.12 or later:

```sh
python -m unittest discover -s scripts -p test_update_citations.py
python scripts/update_citations.py
```

Windows environments without an IANA timezone database need the `tzdata` package. An optional `--proxy` argument can be used locally; proxy settings are never saved in the repository. Python scripts and this documentation are excluded from the generated site.
