# Historical match data

The current personal research dataset contains 120,460 raw singles records: 62,895 ATP and 57,565 WTA rows in 44 annual files covering 2005–partial 2026. The original 117,996 rows in 42 files remain unchanged; their manifests are archived under `snapshots/2005-2025/`. It is real historical data, not generated examples. Raw counts precede exclusion of incomplete matches and other training-quality checks.

Original author: **Jeff Sackmann / Tennis Abstract**. Source README snapshots in this directory preserve the original attribution and **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** notice. Attribution, noncommercial use, and share-alike conditions apply. The dataset's license is separate from application code. No commercial-use permission is claimed.

The small manifests pin source revisions, file URLs, SHA-256 checksums, row counts, and retrieval time. Full CSVs and derived artifacts remain ignored locally to avoid large-file commits. No API keys are required to restore them:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=backend/src python -m data.licensed_history --tour both
```

The downloader verifies every file against its committed checksum. Repeated runs reuse matching files without changing them and fail on conflicts, preserving existing data. It never silently replaces local files. Existing acquisition manifests are also preserved. Extended reviews receive separate hash-named local manifest snapshots. The default end year follows the reviewed manifest; unreviewed years are refused. Requested subsets remain available with `--start` and `--end`.

ATP tournament dates range from 2005-01-03 to 2026-05-25; WTA dates range from 2005-01-03 to 2026-04-21. The 2026 files are incomplete seasons. These are tournament-start dates, not exact match timestamps. A full year filename does not guarantee complete coverage. Missing or stale results, retirements, duplicate matches, temporal leakage, and current-player coverage must be audited before interpreting model accuracy. The [personal engine guide](../personal-engine.md) documents completed training, data exclusions, and measured chronological evaluation.

Sources are pinned to `Kadantte/tennis_atp@712be0c5ade693cdab9e69c23a71a0edf5a23c44` and `VictorSquidWei/tennis_wta@85ef6efaa04ca860ed592a935498dcda9460ea91`. The mixed-source mirror previously configured in the general downloader was not used; it did not expose an explicit license file during inspection.

The 2026 extension was found directly in these existing licensed mirrors, not by changing the pinned revisions. Both README hashes matched the preserved license notices before download. Original-repository 404 responses had previously been overinterpreted; they did not rule out available mirror data. The updated audit is `history-quality-with2026-20261015.json`, and the previous audit remains preserved.
