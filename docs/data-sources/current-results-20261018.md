# Reviewed 2026 result refresh

## Free source selected

[TennisMyLife's match database](https://stats.tennismylife.org/tennis-match-database) explicitly publishes individual ATP/WTA CSV downloads and shell/PowerShell commands for bulk downloading. This is a publisher-provided data export, not a scraper of official tour pages. The reviewed files are `2026.csv`, `ongoing_tourneys.csv`, `2026_wta.csv`, and `wta_ongoing_tourneys.csv` under that site's `/data/` directory. The October 18 snapshots include ATP records dated through October 17 and WTA tournament-date records through October 12. A snapshot retrieval date is not an exact match completion timestamp or a claim of complete tour coverage.

The download page labels its license MIT; the upstream project's [preserved README](result-source-reviews/TML-UPSTREAM-README.md) states: “All data usage is non-commercial unless explicitly permitted.” This integration stays within noncommercial personal research, preserves attribution and that restriction, and does not claim commercial rights. Original Sackmann/Tennis Abstract files retain their separate CC BY-NC-SA 4.0 conditions. No provider purchase or key was needed.

`result-extensions-20261018.json` pins every reviewed CSV's SHA-256, public source URL, source notice and review identifier. TennisMyLife URLs are mutable: `20261018` is our local snapshot review identifier, not a publisher API version. Raw bytes and the source-page capture are retained privately under `data/raw/extensions/` and in backups. A changed download fails verification instead of replacing data or silently changing a checksum. Future reviews must save new immutable snapshots and preserve the prior ones.

## Other sources investigated

- Current licensed Sackmann mirrors still stop May 25 ATP / April 21 WTA. Recent-looking repository activity did not establish newer result files.
- Kaggle's `dissfya/atp-tennis-2000-2023daily-pull` v1222 declares CC0 and reaches October 6, but lacks detailed point counts. `bwandowando/womens-tennis-association-matches-1975-present` v30 declares Apache 2.0 and reaches September tournament starts. These were reviewed as result-only fallbacks; they are inactive in the final manifest. Their experimental model artifacts/reports remain private and are not the deployed models.
- Official WTA website terms prohibit automated harvesting without separate written permission; no direct historical WTA-site collector was added. ATP official pages and tennis-data.co.uk returned access denials; those restrictions were not bypassed.
- The live ESPN integration continues to provide supported fixtures and settle genuine prospective records. A readable endpoint was not treated as a bulk historical-data reuse license.

Publisher-declared licenses and the source download notices are the evidence for this research integration; they are not a blanket commercial sublicense for every upstream provider.

## Identity and quality controls

All source player IDs remain provider-specific. Incoming full names or initials must resolve uniquely to an existing historical player identity; no fuzzy match or synthetic player identity is created. Ambiguous/new identities remain excluded and counted. Results from qualifying, lower tiers and incomplete/retired/defaulted matches are withheld by the adapters and validation rules. The original historical prefix is never rewritten. Potential same-pair duplicates across the tournament-start-date boundary are withheld conservatively, even where this may omit a legitimate rematch. Conflicting perspectives are rejected.

The WTA Kaggle fallback illustrates an ordering trap: draw-order team names do not follow perspective player IDs. Its separate pinned player-ID export resolves that ordering; tests prevent using draw names as the winner label. The final TennisMyLife adapter uses full winner/loser names and carries supplied count triplets, ranking points and demographics without manufacturing missing values. Invalid/incomplete point totals do not update serve/return state. Missing rankings cannot become rank 1.

## Temporal validation and live state

Only 2026 rows strictly after each original source cutoff are appended. Existing 2005–2025 training, selection and calibration data are unchanged. The annual protocol remains fit through 2023, select on 2024, calibrate on 2025, and freeze estimators throughout the 2026 test. Refitting those stages on the expanded history deliberately does not fit on 2026 labels. New 2026 outcomes refresh forward-only ratings/form/statistics and extend the held-out test population.

The existing 21-day result-availability embargo is retained because sources mix match dates and tournament dates and lack independently certified completion times. Consequently, the latest ingested date differs from the latest result allowed into current player state; recent downloaded matches remain pending. Reports expose observed statistics dates and applied feature-state dates separately. Predictions retain the existing dashboard warning field, including partial coverage and player-specific stale/missing form, serve/return or ranking observations. EV guards use the oldest relevant player observation rather than a fresh global download date.

The original test probabilities must reproduce exactly before deployment. A second comparison uses identical later matches after the entire old history's 21-day embargo, comparing refreshed forward-only state with the preserved stale-state model. Both sides use identical match format, including five-set ATP matches. Date-block bootstrap intervals and accuracy, Brier score, log-loss and ECE are retained. Different test populations are not compared as proof of improvement, and candidates are saved without changing active pointers until validation finishes.

## Reproduction

Use the pinned Python constraints from `docs/model-validation/constraints.txt`. `pipeline.personal_data.load_history(tour)` verifies original files, acquires only explicitly reviewed extension files, audits exclusions, and appends accepted rows. `load_history(tour, include_extension=False)` retains the exact original baseline dataset.

Train candidates without deployment from the repository root:

```python
from pipeline.personal_train import train
report = train("atp", test_year=2026, activate=False)  # repeat for wta
```

Run `python -m pipeline.result_update_study --tour atp --baseline <preserved-version> --candidate <candidate-version>` with `PYTHONPATH=backend/src`, `OMP_NUM_THREADS=2`, and `OPENBLAS_NUM_THREADS=2`. The command writes a timestamped private report and does not change active pointers. After required checks, `activate_version(tour, version)` atomically selects a retained artifact. Source files, data, model versions, reports, and consistent SQLite backup-API snapshots must be backed up before and after updates. No live or historical prediction records are manufactured by importing results.

## Final same-day snapshot and quality gate

A second public snapshot review later on October 18 captured the completed Shanghai final and one additional completed WTA record. The new local review identifier is `2026101816`; the earlier reviewed snapshots remain on disk and inactive in the manifest. The annual files were unchanged. The ongoing exports were verified to append rows without revising prior rows. Both new rows were still inside the 21-day embargo, so mature feature state and every evaluated probability remained unchanged. The final artifacts retain the freshly trained estimator/calibrator and record their parent trained version; rebuilding the chronological player state proves exact equivalence before selecting the new snapshot metadata. No embargoed label was used for training, calibration or test scoring.

The audit found birth-date-like values in a small number of source height fields. They are preserved in raw bytes but rejected as impossible demographics; height must be 100–250 cm and age 12–65 years. Missing/invalid observations leave the previous valid state intact. These are physical/schema validity rules, not thresholds optimized against held-out accuracy. The affected exploratory candidates were never activated and remain archived, alongside the corrected candidates and audit. This makes clear why a newly dated source is not automatically fit for deployment.

The schedule bug found during verification is separate from historical training: daily ESPN indexes expose future events absent from its range response. Eight bounded, cached UTC day requests now cover the seven-day horizon, with fixture-ID deduplication and newer-status supersession. No extra historical ESPN bulk collector was introduced. The `BNB Ningbo Open` alias is supported by the already-preserved October 16 official calendar review; unknown ATP surfaces remain unavailable.
