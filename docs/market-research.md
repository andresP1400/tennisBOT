# Independent predictions and sportsbook research

Checked October 16, 2026, approximately 12:48 p.m. America/Toronto (16:48 UTC). The personal research application works for supported fixtures. No profitable strategy or 80% win rate at the requested prices has been established. Earlier model versions, forecasts, losing results, source manifests and reports remain preserved.

Continuation: [surface-context ablation results](context-research-results.md) and [private backup/recovery instructions](private-preservation.md). These add measured research and preservation guidance without deploying a candidate or weakening category guards.

## Operational features and blockers

| Capability | Implemented and verified | Remaining limit |
| --- | --- | --- |
| Independent ATP/WTA predictions | Calibrated models, surface Elo, opponent-adjusted result/serve/return statistics, recent form and strength-of-schedule differences; genuine ESPN fixtures | History stops May 25 ATP / April 21 WTA tournament starts. October player state is stale. Eight reviewed tournament identities and minimum player coverage restrict the draw. |
| Separate value categories | A requires probability >=80% and initially decimal odds >=1.40 (-250 or better); B allows broader probabilities; both require positive conservative net EV | Both correctly show **No qualifying opportunities.** Fresh history, admissible prices and adequate validation are missing. |
| Multi-book comparison | Optional The Odds API adapter, paired de-vigging, equal-weight consensus, best net prices, source/observation times, exact fixture binding and same-book movement | No usable key is configured. Parser/budget tests pass, but credentialed live ingestion remains unverified. Feed prices do not guarantee user access or execution. |
| Opening/closing observations | Explicit archive fields, closing quotes excluded from decisions | The adapter collects current moneylines only. Certified opening/closing collection is missing. First/last observed never becomes official open/close. No actual CLV is available. |
| Public betting intelligence | Attributed manual entry, provider interface, publication/observation times, ticket/money differences and descriptive reverse movement | No authorized tennis split feed or historical panel. No incremental prediction/ROI effect measured. Money share does not identify sharp bettors. |
| Automatic tracking | Five-minute independent worker, append-only SQLite constraints, stable selection IDs, durable original forecast/price references | The host must remain awake. Git does not back up private records. Browser visits never trigger paid calls. |
| Prospective market evaluation | Separate A/B accuracy, Brier, log loss, calibration gap, paper returns, drawdown, buckets, benchmarks and planned milestones | No real category picks exist. ROI, intervals and CLV remain null when evidence is absent. No wagers are placed. |
| Model research | Logistic, histogram boosting, XGBoost, LightGBM, CatBoost and a fixed equal-weight calibrated ensemble actually evaluated | Partial-2026 is an already inspected retrospective out-of-sample period. No candidate was activated. No newly untouched period is available. |

Production startup, proxy and actual Chromium tests returned two ATP and six WTA forecasts; counts change as matches start. Unsupported fixtures remain explained. All six worker phases (predictions, settlement, markets for each tour) succeeded. A successful market phase with the provider disabled does not mean paid prices were retrieved.

## Real historical results

The complete [aggregate study](model-validation/market-study-20261016.json) retains all candidates, including worse results, source audits, calibration bins, high-confidence coverage and paired comparisons. The [protocol](market-research-protocol.md) preceded this study. Fixed estimator settings are in `pipeline/market_learners.py`.

Train through 2023, select using 2024 raw log loss, calibrate on 2025, test available partial-2026 matches. Preprocessing fits within training. Symmetrization precedes calibration in research and serving. The existing 21-day result-availability embargo uses tournament start dates, an approximation because true completion times are absent. No current odds or public splits enter independent model features.

| Tour / model | Matches | Accuracy | Brier | Log loss |
| --- | ---: | ---: | ---: | ---: |
| ATP deployed histogram boosting | 1,406 | 66.15% | 0.21075 | 0.60874 |
| ATP calibrated surface/global Elo | 1,406 | 65.36% | 0.21857 | 0.62624 |
| ATP fixed ensemble, selected on 2024 | 1,406 | 66.64% | 0.21018 | 0.60733 |
| WTA deployed logistic | 957 | 66.25% | 0.21013 | 0.60639 |
| WTA calibrated surface/global Elo | 957 | 65.20% | 0.21377 | 0.61391 |
| WTA fixed ensemble, selected on 2024 | 957 | 66.46% | 0.20928 | 0.60379 |

Approximate paired 95% accuracy-difference intervals for the ensembles versus deployed models include zero: ATP -0.56 to +1.61 percentage points; WTA -0.98 to +1.40 points. Brier/log-loss difference intervals also include zero. These comparisons do not establish reliable improvement; deployed pointers and model bytes remain unchanged. The study adds signed/symmetric prior-match-count coverage proxies, not a fitted Bayesian rating posterior.

At the fixed >=80% predicted-winner cutoff, unchanged deployed models won ATP 111/128 (86.72%, 9.10% coverage) and WTA 96/110 (87.27%, 11.49% coverage), with mean probabilities 85.75% and 85.24%. Approximate tournament-date-block 95% accuracy intervals were ATP 81.95–92.56% (18 blocks) and WTA 82.28–92.13% (13 blocks). These are small retrospective **probability-only subsets**, without contemporaneous prices: **not Category A results**, no demonstration of 80% at -250 or better, no ROI or CLV evidence. Cross-date player dependence remains unmodeled.

Live results are separate. At this check, first-ever forecasts across versions won 1/3 ATP and 6/14 WTA: 7/17 combined (41.18%), plus one WTA void. Current deployed versions won 1/2 ATP and 4/8 WTA: 5/10 combined. These are small, changing samples with existing staleness/coverage limitations. Repeated model versions are not independent completed matches. Poor earlier results remain in the ledger.

## Admission and uncertainty

The fixed policy requires history <=30 days old, two distinct current paired bookmakers, source quotes and local observations <=300 seconds old, pre-start timing, exact fixture/player identity and plausible paired margins. Absolute model/consensus discrepancy >0.20 is blocked for review. WTA 125 remains unvalidated and blocked. Conservative probability must exceed consensus by >=0.02 and produce positive net EV after known commission. Unknown exchange commissions block price selection. Category A additionally requires p>=0.80 and initially decimal price>=1.40. `TENNISBOT_VALUE_MIN_DECIMAL_ODDS` changes the filter and policy hash, retaining old decisions.

Raw EV=`p*decimal_odds-1`; net and conservative EV are separate. Fair decimal odds=`1/p`; raw implied probability=`1/odds`. Consensus de-vigs each book's actual pair before averaging; it differs from cross-book best prices. Missing quantities remain unavailable. Positive point EV never overrides a failed guard.

Versioned local evidence binds to model, source digest and implementation fingerprint. Fixed confidence bins need >=100 canonical matches and >=20 tournament-date blocks before supplying approximate win-frequency bounds; underdog bounds reverse with side. These are calibration-bin frequency intervals, **not individual-match guarantees**. Corrupt, sparse or mismatched evidence fails closed. Neither tour has an admissible >=80% bin in this small partial-2026 dataset; WTA has no admissible bin. Descriptive subset intervals above cannot override these admission rules.

Verified injuries, exact fatigue/rest timestamps, indoor/outdoor metadata and longitudinal development features are unavailable, not simulated or reported as implemented. Rating uncertainty remains incomplete. Fresh licensed history and broader chronological calibration validation are blockers independently of an odds key. No available historical period is certified newly untouched; future uninspected, timestamped prospective matches are needed for confirmation.

## Optional feeds, manual entries and costs

Core fixtures, predictions, tracking and results need no credentials. Leave paid collection disabled unless you have authorized access and accept current provider terms/pricing. Keep keys only in ignored `local.env` or secure environment settings, never chat or Git.

To enable the adapter, set `TENNISBOT_MARKET_ODDS_ENABLED=true`, supply `ODDS_API_KEY`, and copy at most four explicit current sport keys from the provider catalog into comma-separated `TENNISBOT_MARKET_SPORTS`. Allowed keys have the form `tennis_atp_...` or `tennis_wta_...` with lowercase letters, digits and underscores. Do not invent keys. Only matching tours are requested, using US-region decimal h2h markets; availability and user access vary by jurisdiction/book.

`TENNISBOT_MARKET_REQUESTS_PER_DAY` defaults to 10 HTTP calls across tours. Admissions persist before I/O; restarts cannot reset the cap, and each sport has a five-minute cooldown. Failed calls consume an admission. This is a request cap, **not guaranteed monetary/provider-credit cost control**. Other legacy integrations are separate and not covered. No paid historical endpoint, bookmaker scraping or bet execution is enabled.

Official sources checked normally with TLS on October 16: [The Odds API v4 guide](https://the-odds-api.com/liveapi/guides/v4/) and [tennis coverage](https://the-odds-api.com/sports-odds-data/tennis-odds.html) returned HTTP 200 and document moneylines; no usable ticket/money feed was obtained. [SportsDataIO betting-data overview](https://sportsdata.io/betting-data) returned 200, while the investigated tennis API-documentation URL returned 404. This does not establish authorized tennis split coverage. No access restrictions were bypassed.

`POST /api/personal/markets/manual-quote` and `/manual-split` retain attributed observations. Server-stamped manual provenance cannot impersonate the provider; manual quotes cannot qualify either category. Public percentages require source, scope, publication/observation times and fixture linkage. The private backend's `/docs` describes request shapes; copy fixture identity from a real API response. The actual server clock rejects new post-start/backdated inserts.

## Prospective tracking and evaluation

`GET /api/personal/markets?tour=atp` (or `wta`) returns categories, assessed sides, comparisons, guards, public observations and category summaries across both tours. The dashboard keeps **80%+ High-Confidence Value**, **Best Value Opportunities** and **All Match Predictions** separate. The browser expires opportunities at the earliest price expiry, match start or one-minute deadline and clears them on failed refresh. The worker archives qualifying decisions without browser access.

`GET /api/personal/value-performance?category=A` (or `B`) scores the first-ever selection per unique fixture/category. Optional `policy_version` labels a subset without deleting older results. A match can qualify both categories; do not add those results as independent portfolio bets. Selections retain original forecast/quote IDs, model/policy versions, probabilities, price times, uncertainty method/digest, EV, evidence and risks; repeated revisions cannot select a favorable price retrospectively.

Actual provider outcomes settle unit-stake paper returns net of known commission. Retirements, defaults, cancellations and walkovers are conservatively void. Book-specific partial-completion/retirement rules, fills and slippage remain missing. Thus paper returns at observed prices are not realized account profit. CLV requires explicit archived same-book closing pairs; otherwise null. The current provider does not supply them automatically.

Benchmarks use independent Elo probabilities, archived no-vig consensus, favorite-at-archived-price returns and analytic probability-weighted random-side expected returns. The randomized baseline is an expectation, not fabricated forecasts/outcomes. Fixed odds/confidence/surface/tour buckets retain empty and losing groups. Drawdown uses provider settlement-observation order and unit stakes. Date-block bootstrap ROI intervals require >=30 completed matches and >=20 date groups; sparse samples have no interval.

Planned first-100/250/500/1000 eligible-pick checks wait for all first picks to settle, retaining losses and voids. Approximate adjusted ROI intervals use alpha=0.05/8 (two categories/four looks); dependence/bootstrap limitations remain. Descriptive dashboard metrics are not repeated significance tests. No actual historical odds/split panel exists to run a real betting or public-signal backtest. Positive estimated EV or paper ROI does not automatically establish an advantage.

## Reproduce and run privately

Follow the [Mac instructions](mac-daily-use.md): build, run `python start_all.py --production`, then `open 'http://127.0.0.1:3000/dashboard'` for an application running on your Mac. A cloud loopback address is not a remote Mac-access URL; no public deployment/tunnel exists. Optional market settings are in `.env.example`.

After restoring licensed history and training personal models under the 2026 protocol, reproduce research with:

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/backend/src"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
python -m pip install -r requirements-market-research.txt
python -m pipeline.market_study --tour both
```

CatBoost is pinned and optional for research; daily serving does not need it. This creates a new private timestamped report and version-specific validation evidence, without deploying candidates. Conflicting evidence is preserved and rejected. Deployed metrics must reproduce exactly before evidence is saved; a model trained under a different protocol is not silently treated as matching.

History remains 44 checksum-verified files: 120,460 raw / 115,975 eligible matches, including the original 117,996 records; pinned downloads and CC BY-NC-SA attribution remain intact. No raw datasets or model weights are newly committed. Private records live in `reports/personal/prediction-events.sqlite3`; keep consistent SQLite backups and every model version outside Git. Source/aggregate results in GitHub do not include private records.

Checks: 203 backend tests, 34 frontend tests, strict mypy over 134 sources including the launcher, Black/Ruff, TypeScript/ESLint, dependency checks, full production build and real browser/API validation. Synthetic unit fixtures exercise guards only; reported performance and displayed forecasts use real records. This does not establish fresh October statistics, complete coverage, credentialed feeds, book-specific settlement, an untouched new test or profitable operation.
