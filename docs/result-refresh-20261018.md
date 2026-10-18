# October 18 historical-data refresh

The existing prediction architecture and dashboard build are retained. A reviewed free TennisMyLife export adds **985 ATP** and **1,275 WTA** completed main-tour results to the original immutable history, including available detailed point counts, rankings and demographics. Dataset attribution, explicit download permission, noncommercial restrictions, immutable snapshot hashes and exclusions are documented in [the source review](data-sources/current-results-20261018.md). No subscription was purchased or required.

## Coverage and actual usable state

| Tour | Latest accepted source date | Date precision | Latest applied feature-state date |
| --- | --- | --- | --- |
| ATP | 2026-10-18 | Provider result-date field; completed Shanghai final included | 2026-09-27 |
| WTA | 2026-10-12 | Tournament-start date; the completed October 18 Wuhan final is included in that event | 2026-09-27 |

These dates do not establish complete tour/player coverage. Ambiguous identities, possible overlaps, lower tiers and incomplete results remain excluded. Missing/invalid counts are not fabricated. Some source height fields contained birth-date-like integers: physical plausibility checks reject them and preserve previous valid observations. The raw bytes and rejected experimental candidates remain in the private archive.

The 21-day availability embargo remains in place. It intentionally prevents the newest source outcomes from entering ratings/form/serve/return state or test scoring until mature. Fresh download dates therefore do not imply fully current player features. Each available forecast displays partial-coverage/embargo warnings, and stale/missing player-specific form, serve/return or ranking observations continue to block EV admission.

## Frozen chronological evaluation

Fitting remains through 2023, selection on 2024, calibration on 2025, and frozen out-of-sample testing on 2026. Refitting the existing stages on the expanded history does not fit on 2026 outcomes. The newly admitted outcomes update forward-only player state and extend the untouched test cohort. No 2026 labels recalibrate or select a model.

The **original test probabilities and metrics are unchanged**: ATP 66.15% accuracy on 1,406 matches; WTA 66.25% on 957. The larger, different 2026 population through September 27 scores:

| Tour | Matches | Accuracy | Brier | Log-loss | ECE (10 bins) |
| --- | ---: | ---: | ---: | ---: | ---: |
| ATP | 2,249 | 65.72% | 0.21292 | 0.61348 | 0.02603 |
| WTA | 2,091 | 65.76% | 0.20898 | 0.60378 | 0.02429 |

The larger-population percentages must not be compared directly with the original smaller-cohort percentages as proof of improvement or regression. Calibration is reported rather than optimized on the test set.

On the **same later matches**, after the old history's entire embargo window:

| Tour | Later matches | Refreshed-state accuracy | Preserved stale-state accuracy | Paired accuracy difference, approximate 95% interval |
| --- | ---: | ---: | ---: | --- |
| ATP | 792 | 65.53% | 65.78% | −0.25 percentage points [−1.63, +1.16] |
| WTA | 1,044 | 65.13% | 65.04% | +0.10 percentage points [−2.12, +2.22] |

There is **no statistically clear accuracy improvement**. ATP Brier/log-loss point estimates improve slightly; WTA's change is essentially neutral/slightly worse. Loss intervals also include zero. These retrospective, date-block bootstrap intervals do not remove dependence between players/events or establish prospective reliability/profitability. Full aggregate numbers and provenance are in [the evidence JSON](result-refresh-evidence-20261018.json); private versioned reports preserve all trial results, including failed quality checks.

## Daily predictions and retention

The old range-only ESPN query omitted next-week tournaments that individual day indexes exposed. The schedule adapter now checks eight cached UTC day indexes with bounded concurrency, deduplicates fixture IDs and lets newer statuses remove outdated scheduled rows. Tests preserve genuine quote observation times and the exact seven-day timestamp cutoff. The already-reviewed Ningbo identity now accepts its calendar's explicit `BNB Ningbo Open` display name. No ATP surface is guessed from another season or coincident provider ID.

At production verification the dashboard displayed **22 genuine upcoming WTA forecasts** with calibrated probabilities, current model versions, pre-match timestamps and SQLite record IDs. **ATP had zero eligible forecasts**: 28 future fixtures were available but their tournament surfaces remain unreviewed. They are shown as unavailable, not assigned synthetic probabilities. Counts change as draws are published and matches start.

The background worker remains healthy and polls every five minutes without a browser. All seven forecast payloads present immediately before deployment survived byte-for-byte; the new WTA forecasts were appended, and the three already completed outcomes remain intact. A headless browser verified both tour views, updated historical labels, all displayed tracking IDs and input-freshness warnings. No records were invented or backdated; new models do not erase the original live results.

Active artifacts at this checkpoint:

- ATP `atp-20261018T161334638405Z-7d3b04695bed`
- WTA `wta-20261018T161409043263Z-73dc03b25069`

The final same-day provider append contained only embargoed outcomes. Exact mature-state equality and unchanged evaluation probabilities were checked before retaining the freshly fitted estimator/calibrator in the final snapshot artifacts; parent trained versions are recorded. All older models and private archives are retained.

## Validation and private recovery

238 backend tests passed; strict mypy checked 143 source files; Black, Ruff, import smoke and secret checks passed. The existing unchanged frontend production build served successfully; it was not rebuilt. The dashboard's ATP/WTA views were checked in Chromium. There is no claim of 2026 test-set tuning or a new prospective accuracy guarantee.

Before and after this update, private source/model/data/report archives and consistent SQLite backup-API snapshots are saved under `/workspace/tennisbot-backups`. The archive manifest records source commit, individual SHA-256 hashes and ledger table counts. Extracted-backup verification must load both active models, verify SQLite integrity/counts, and reproduce preserved forecast probabilities. Keep an independent private copy outside this cloud machine; workspace backups alone do not survive loss of the environment.

On the machine running the services, use the existing `python start_all.py --production` launcher and the `/dashboard` route on port 3000. No public preview or remote tunnel is configured. For a Mac, securely transfer the verified private archive and checksum, extract into a new empty directory, then follow `OPEN-DASHBOARD.md` in the archive and [the Mac guide](mac-daily-use.md). Do not retrain or overwrite a separate local prediction ledger merely to open the dashboard.
