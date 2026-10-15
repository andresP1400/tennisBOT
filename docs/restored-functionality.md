# Restored TennisBOT functionality

The unavailable task's reported 80/17 test counts are not evidence of code available in this repository. The verified starting revision was `207fbd0` (53 backend/13 frontend tests). The following functionality has been implemented and tested here; this does not claim recovery of the original implementation.

| Requested improvement | Current implementation | Automated evidence |
| --- | --- | --- |
| Temporal validation / preprocessing leakage | Real-data 21-day availability embargo and chronological train/selection/calibration/test stages; legacy stacking fold-local transforms and inner chronological tuning/stopping | `test_personal_engine.py`, `test_personal_settlement.py`, `test_restored_validation.py`, `test_leakage.py` |
| Calibration consistency | Symmetric logit Platt for personal models; shared symmetrization-then-calibration for legacy batch, history, and live prediction | `test_restored_validation.py`, `test_personal_engine.py` |
| Bookmaker consensus | Per-book paired de-vigging, equal-book averaging, relay deduplication, correct player orientation; best execution prices kept separate | `test_market_safeguards.py` |
| Optional recent form | `python -m pipeline.personal_train --no-recent-form`; schema/form flags survive serialization and inference | `test_opponent_features.py` |
| Guarded expected value | Freshness/provenance/market-depth/edge/commission admission, quarter Kelly capped at 1%, zero stake when blocked | `test_market_safeguards.py`, frontend `personal-ev.test.tsx` |
| Versioned models | Immutable timestamped tour artifacts, source/implementation fingerprints, feature order, runtime versions, atomic active pointer | `test_opponent_features.py` |
| Historical evaluation | Real 2024–2025 one-match-one-row metrics, Elo/ML/calibrated/uncalibrated baselines, yearly/surface breakdowns, retained older reports | `docs/model-validation/{atp,wta}.json`, actual reproducible training |
| Production / dependencies | System fonts remove Google downloads; requirements/dev dependencies and model-library constraints; strict typing | Full production build, import smoke test, mypy, TypeScript/ESLint |
| Comprehensive verification | Tests target leakage, market arithmetic, persistence, timestamps, settlement, and availability rather than matching old counts | Full backend/frontend suites |

Real-data training uses all 42 checksum-verified licensed source files (117,996 raw records; 113,612 eligible completed matches after exclusions). Match-level data, model bytes, and private SQLite forecasts remain ignored by Git; pinned download manifests, attribution, reproduction instructions, and aggregate evaluation reports are committed.

Surface-specific Elo and opponent-adjusted form/serve/return statistics feed CPU logistic/gradient-boosting candidates. Family selection uses only 2022 log-loss; calibration uses 2023; 2024–2025 estimators remain frozen. These years have been inspected during development, so the results are retrospective held-out evaluation, not a newly blind experiment. Adding features has not improved every metric and does not establish profitable betting.

The dashboard/API return actual covered ATP/WTA upcoming fixtures with a winner, probability, model version, pre-match timestamp, and durable record ID. Unknown players/surfaces stay unavailable. A background worker records and settles forecasts without an open browser. All-version live results remain visible after model changes; older bad results are retained.

Remaining constraints: no 2026 history in the permitted snapshot; upstream 2026 CSV probes returned 404; current confirmed surfaces cover Shanghai ATP and Wuhan WTA only; provider fixtures/outcomes/odds may be absent or unavailable. Fresh permitted historical results and reviewed surface identities are needed for wider, current coverage. The core engine needs no credentials. Optional sportsbook accounts/keys can add markets but cannot solve stale tennis history.

## Verified checks

On 2026-10-15, **116 backend tests and 18 frontend tests passed**. Strict mypy checked 109 source files; Black, Ruff, frontend TypeScript, ESLint, dependency consistency, secret scanning, and import smoke checks passed. The complete optimized Next.js production build passed with system fonts. Two real-data schema-2 training reruns reproduced identical evaluation metrics for both tours with the installed libraries. Production backend health and the dashboard returned HTTP 200; requests through the frontend proxy returned genuine supported forecasts, normalized probabilities, current versioned models, and persisted tracking IDs. Current stale-input EV analyses had zero suggested stake.

These checks establish the implemented behavior and measured retrospective results. They do not establish profitable betting, fresh 2026 player state, comprehensive tournament coverage, or performance on a new blind future sample.
