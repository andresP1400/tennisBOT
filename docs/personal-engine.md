# Personal ATP/WTA prediction engine

This engine uses real match history and local CPU models. It does not require sportsbook, LLM, or research-provider keys, and never substitutes simulated forecasts when historical coverage is missing.

## Reproduce training

Use Python 3.12 and the repository's requirements. From the repository root:

```bash
source /workspace/tennisbot-venv/bin/activate
export PYTHONPATH=backend/src
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
python -m data.licensed_history --tour both
python -m pipeline.personal_train --tour both --test-year 2026
```

On a fresh machine, create a virtual environment and install `requirements.txt` and `requirements-dev.txt` first. To use the measured model-library versions, run `pip install -r requirements.txt -r requirements-dev.txt -c docs/model-validation/constraints.txt`. The downloader restores exactly the reviewed files and refuses conflicting existing files. See [data provenance and license](data-sources/README.md). The data is licensed **CC BY-NC-SA 4.0**, attributed to Jeff Sackmann / Tennis Abstract, and is used here for personal noncommercial research.

Each training run creates new versioned model and audit files under `models/saved/personal/` and `reports/personal/{tour}/`. Earlier versions are retained. Artifacts include feature-schema/form flags, source digests, implementation hashes, and runtime library versions. Only the active-version pointer is replaced after saving the new artifact. These files are local and ignored by Git. Re-running training twice produced identical measured accuracy, Brier scores, and log-loss with the installed libraries.

## What was measured

The current reviewed snapshot contains **120,460 raw matches in 44 annual files (2005–partial 2026)**: ATP 62,895 and WTA 57,565. The original 117,996 rows and 2005–2025 manifests remain preserved; the extension adds 1,449 ATP and 1,015 WTA records. All file bytes, row counts, and source README license hashes are verified. The [new suitability audit](data-sources/history-quality-with2026-20261015.json) excludes 2,320 ATP and 2,165 WTA rows, leaving 60,575 and 55,400 eligible completed matches. No duplicate identities, missing player IDs, identical opponents, or invalid dates were found.

Valid serve-point counts for both players exist in 56,017 eligible ATP and 45,395 eligible WTA matches. Missing, partial, negative, nonfinite, or contradictory point statistics are skipped, never converted to zero wins. Their valid match outcomes still contribute to Elo/form. Missing demographics affect 2,416 ATP and 9,986 WTA eligible rows. `python -m data.history_quality` creates a timestamped audit without replacing earlier reports. Completeness is relative to the pinned files, not every match played worldwide.

The licensed mirrors already contained the 2026 files at the pinned revisions. Earlier 404 checks against the unavailable original repositories did not establish that these mirror files were missing. Their source README hashes match the original license snapshots. ATP tournament-start dates reach **2026-05-25** and WTA dates reach **2026-04-21**; these are partial seasons and do not supply current October results. New files use the existing filenames only when absent; conflicts still fail without replacement. Each extended acquisition review gets a separate immutable manifest snapshot, while the original local manifest survives.

The deployed annual protocol was fixed before scoring the new 2026 holdout:

- 2005–2007: rating/history warmup.
- 2008–2023: estimator fitting and training-only scaling.
- 2024: select logistic regression or histogram gradient boosting by log-loss.
- 2025: fit symmetric Platt calibration.
- Available 2026 completed matches: out-of-sample test with frozen estimators and calibration. No 2026 labels enter any fitting stage; player summaries update forward as earlier results become available.

Source dates are tournament starts, so results remain embargoed for 21 days before updating Elo, form, ranking, serve/return, or opponent-adjusted statistics. Fitting-stage labels whose embargo crosses the next stage are excluded. The delay is a conservative availability assumption, not a verified completion timestamp. Player-order augmentation is training-only; mirror rows never inflate test counts. Source coverage and supported fixture coverage are separate.

| Tour | Selected model | 2026 test matches | Calibrated ML accuracy | Brier | Log-loss | ROC-AUC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ATP | Histogram gradient boosting | 1,406 | 66.15% | 0.2107 | 0.6087 | 0.7293 |
| WTA | Logistic regression | 957 | 66.25% | 0.2101 | 0.6064 | 0.7289 |

The same historical minimum-coverage policy used by live inference (at least ten mature prior matches per player) covers 1,177 ATP matches at 65.93% and 862 WTA matches at 66.24%. Full reports retain both populations; provider identity/surface availability imposes additional live restrictions. WTA 125 performance is not established by these main-tour reports.

The original frozen protocol fitted through 2021, selected on 2022, and calibrated on 2023. On the **same 2026 test matches**, it scored 66.57% ATP and 66.14% WTA. The annual models' paired accuracy differences are −0.43 percentage points (approximate 95% interval −1.61 to +0.63) and +0.10 points (−0.38 to +0.77). Intervals include zero; a clear improvement over the original model has not been established. Different test periods/populations must not be compared as evidence of improvement.

## Annual walk-forward validation

```bash
python -m pipeline.personal_walkforward --tour both --start-year 2022 --end-year 2026
```

Each year independently fits through year−3, selects on year−2, calibrates on year−1, and freezes the model throughout the test year. This command writes separate timestamped reports and never changes a deployed model pointer. Five annual tests pool to:

| Tour | Unique test matches | ML accuracy | Approximate 95% date-block interval | Brier | Log-loss |
| --- | ---: | ---: | ---: | ---: | ---: |
| ATP | 12,857 | 65.79% | 64.64%–66.94% | 0.2129 | 0.6133 |
| WTA | 11,314 | 65.49% | 64.50%–66.43% | 0.2145 | 0.6175 |

The [ATP](model-validation/walkforward-atp.json) and [WTA](model-validation/walkforward-wta.json) reports retain every year's scores, selected family, exact stage dates/counts, calibration comparison, coverage, Elo baselines, and paired date-block bootstrap intervals (1,000 resamples, seed 42). Matches sharing a tournament-start date are resampled together; player dependence across date blocks remains. These are approximate retrospective intervals, not independent-match guarantees or a new prospective trial. No betting profitability is measured.

The [current model reports](model-validation/) correspond to the actually deployed 2026-test models. Previous 2024–2025 reports (65.26% ATP / 65.31% WTA) are retained under `previous-2024-2025/`; earlier schema-1 and weaker date-batch reports remain archived. Newer parameters are deployed under the declared annual protocol, not selected by choosing the best 2026 accuracy. Every previous model and live forecast survives retraining.

Schema 2 includes global/surface Elo with small-sample shrinkage, last-20-match form, and opponent-adjusted result/serve/return residuals with frozen pre-event baselines. `--no-recent-form` trains a new version with raw/adjusted result-form fields disabled and records that flag for inference. Calibration is fitted honestly but can worsen held-out scores; single-class AUC is unavailable rather than reported as a fabricated 0.5.

## Run and inspect forecasts

```bash
python -m uvicorn api_server:app --app-dir backend/src --host 127.0.0.1 --port 9090
# In another terminal:
cd frontend
npm ci
npm run build
cp -R public .next/standalone/
cp -R .next/static .next/standalone/.next/
HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/server.js
```

The dashboard's “Upcoming match predictions” panel displays each supported fixture, predicted winner, estimated winning probability, recorded timestamp, model version, and observed odds where available. The model was trained on real outcomes; the displayed historical accuracy is explicitly separated from live performance.

The API polls ESPN's public ATP/WTA scoreboards every five minutes, records predictions, and continues retrying after provider failures. One date-range request per tour covers the next seven days, including newly published tournaments beyond today's scoreboard. UTC dates handle day/year boundaries; the exact seven-day timestamp cutoff is still enforced. Dashboard requests share a five-minute cache. Completed/live matches, doubles, past starts, and unresolved competitors are excluded. Cached quotes retain their original observation timestamps. Unknown or ambiguously matched players and players with fewer than ten historical completed matches are left unavailable. Names are normalized for accents and punctuation without speculative fuzzy matching.

Surface verification currently covers 2026 Shanghai ATP; Wuhan, Osaka, and Ningbo WTA; and Mallorca, Rovereto, Lisbon, and Rio WTA 125 events. The [original calendar review](data-sources/tournament-surfaces-2026.json) and [October 19 event review](data-sources/tournament-surfaces-nextweek-20261016.json) preserve official calendar identities and response hashes. Osaka/Ningbo use hard courts; Rio uses clay. ESPN and WTA use different event IDs, so the registry requires the reviewed tour, provider ID, season, event name, and fixture year to agree. Unknown names/seasons/surfaces remain unavailable. WTA 125 forecasts explicitly warn that historical main-tour accuracy does not establish performance at that level, and fail calibration-provenance admission for EV. Extend the reviewed registry as new tournaments become relevant. Providers may omit fixtures or change their schemas; public endpoint access is not a blanket redistribution license. This is a local personal-use workflow, not a comprehensive licensed commercial fixture feed.

The configured Next.js output is standalone. Copy its public/static assets after each build and use the generated server above; `next start` emits an unsupported-output warning. Stop an existing frontend before rebuilding into its shared `.next` directory.

History now includes partial 2026 results, but current forecasts still omit matches/rankings after the reviewed May ATP / April WTA cutoffs and carry explicit data-age warnings. They demonstrate functioning inference but cannot be assumed to match the historical backtest's quality. Licensed fresh match data and additional verified surfaces are the main remaining coverage improvements. No credential is currently required for the supported workflow.

## Private pre-match tracking

Every forecast is committed before being returned to the dashboard. `reports/personal/prediction-events.sqlite3` stores the fixture identity, scheduled start, UTC prediction time, model version, both win probabilities, Elo probability, data-through date, and any available real market prices, provider, and observation time. Missing odds remain null; provider moneylines are converted to decimal prices in player order. The core engine does not make sportsbook API calls.

Snapshots are append-only: database triggers reject updates and deletions. Changed model versions, prices, probabilities, or scheduled starts create new records. Identical snapshots reuse the first record and timestamp. Writes are transactionally committed with SQLite FULL synchronous mode; the file is readable only by its owner. Old snapshots remain available after restart or retraining. The API never logs forecasts after a match's scheduled start.

The background worker also revisits unresolved fixture start dates and appends provider-confirmed outcomes to a separate immutable table. Exact fixture IDs, both player identities, observation times, and a bounded reschedule window must agree. Only confirmed completed singles with a named winner are scored; retirement/default/walkover outcomes are void. Provider failures leave predictions pending. Polling limits rotate through unresolved dates so old missing events cannot permanently starve later dates.

Live accuracy is displayed separately from the historical backtest. Current-model statistics use the first pre-match snapshot per fixture/model, so changing odds does not inflate the sample. The dashboard also displays the first-ever recorded forecast per unique fixture across all model versions, preventing retraining from hiding poor earlier results. A new model with no resolved forecasts reports no live accuracy. Early live samples can be much worse than the retrospective backtest and should not be interpreted as stable performance. Outcomes come from the cited provider and are not independently notarized.

This is private local persistence, not an external notarization or a guarantee against deletion of the machine. Back up the database using SQLite's backup API and retain the versioned model directory if moving environments. Do not commit the database, datasets, or model artifacts to a public repository. Live processes and periodic polling must restart after restoring an environment snapshot.

Endpoints:

- `GET /api/personal/predictions?tour=atp` (or `wta`): recorded upcoming forecasts and honest availability reasons.
- `GET /api/personal/backtest?tour=atp`: measured results for the deployed model.
- `GET /api/personal/history?limit=100`: exact historical prediction snapshots.
- `GET /api/personal/live-performance?tour=atp`: current-version observed results; add `scope=all` for per-model and unique-fixture all-version results.

Both services bind to loopback for personal use. No web preview, public deployment, credentials, or outbound messages are created by this setup.

## Market consensus and guarded EV

Optional market adapters preserve each bookmaker's complete two-player price pair, including player order. Each pair is de-vigged separately, then those fair probabilities are averaged; cross-book best prices are used only as potential execution prices. Relays with the same bookmaker identity count once. Missing/nonfinite prices never produce a consensus.

Informational EV is `p * (decimal_odds - 1) * (1 - commission) - (1 - p)`. Positive EV alone is insufficient: admission requires known calibration provenance, historical inputs no older than 30 days, quotes observed within five minutes and not in the future, at least two independent paired bookmakers, valid consensus, at least five percentage points of probability edge, and positive EV after commission. Quarter Kelly is capped at 1% of bankroll; every failed guard forces the suggested fraction to zero. These are conservative data guards, not a measured profitable strategy. There is no bet placement.

The personal schedule currently supplies at most one bookmaker and the historical inputs remain stale, so its EV analysis is blocked. Missing quotes show EV unavailable. The dashboard displays reasons and the analysis is retained in each forecast snapshot. The manual legacy probability endpoint has no trusted calibration/freshness provenance and cannot mark a wager eligible. Sportsbook integration remains optional and separate from the core models.

Legacy stacking now also fits transforms inside each chronological outer fold, tunes/stops only on an inner chronological tail, and refits with the selected iteration count before scoring the untouched outer validation fold. Missing raw ages/heights remain missing through feature construction; full-dataset demographic averages have been removed so those future values cannot enter earlier features. All-missing training columns are retained. Adaptive splits preserve whole dates and mirrored matches. Batch evaluation, historical tracking, and live inference use the same symmetrization-then-calibration order. The personal pipeline above is the real-data model serving the dashboard; a synthetic legacy smoke test is not an accuracy measurement.

Later 2026 results still require a permitted, verified source. The most recently reviewed mirrors stop in May/April; recent fork searches did not provide a reviewed later file. Current coverage also needs more confirmed tournament surface identities. Neither limitation is solved by a sportsbook key.
