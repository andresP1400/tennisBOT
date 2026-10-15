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
| Historical evaluation | Annual 2022–2026 chronological tests, paired uncertainty/coverage reports, current 2026 model scores, Elo/ML/raw/calibrated baselines, and preserved older reports | `docs/model-validation/{atp,wta}.json`, actual reproducible training |
| Production / dependencies | System fonts remove Google downloads; requirements/dev dependencies and model-library constraints; strict typing | Full production build, import smoke test, mypy, TypeScript/ESLint |
| Comprehensive verification | Tests target leakage, market arithmetic, persistence, timestamps, settlement, and availability rather than matching old counts | Full backend/frontend suites |

Real-data training originally used 42 checksum-verified files (117,996 raw records); it now uses 44 files with a reviewed partial-2026 extension (120,460 raw records; 115,975 eligible completed matches). Original files/manifests/reports remain preserved. Match-level data, model bytes, and private SQLite forecasts remain ignored by Git; pinned download manifests, attribution, reproduction instructions, and aggregate evaluation reports are committed.

Surface-specific Elo and opponent-adjusted form/serve/return statistics feed CPU logistic/gradient-boosting candidates. The deployed annual model fits through 2023, selects on 2024 log-loss, calibrates on 2025, and tests partial 2026 with frozen estimators. Separate annual tests cover 2022–2026. The earlier frozen 2024–2025 protocol remains reproducible and archived. These years have been inspected during development, so the results are retrospective held-out evaluation, not a newly blind experiment. Adding features has not improved every metric and does not establish profitable betting.

The dashboard/API return actual covered ATP/WTA upcoming fixtures with a winner, probability, model version, pre-match timestamp, and durable record ID. Unknown players/surfaces stay unavailable. A background worker records and settles forecasts without an open browser. All-version live results remain visible after model changes; older bad results are retained.

Remaining constraints: reviewed 2026 history stops at May 25 ATP / April 21 WTA tournament starts, so October player state is still incomplete. Current reviewed surfaces cover five 2026 tournaments; provider fixtures/outcomes/odds may be unavailable. Later permitted results and additional reviewed surface identities remain needed. The core engine needs no credentials. Optional sportsbook keys cannot solve missing tennis history.

## Verified checks

On 2026-10-15, **151 backend tests and 21 frontend tests passed**. Strict mypy checked 116 source files; Black, Ruff, frontend TypeScript, ESLint, dependency consistency, secret scanning, and import smoke checks passed. The complete optimized Next.js production build passed with system fonts. Two real-data schema-2 training reruns reproduced identical evaluation metrics for both tours with the installed libraries. Production backend health and the dashboard returned HTTP 200; requests through the frontend proxy returned genuine supported forecasts, normalized probabilities, current versioned models, and persisted tracking IDs. Current stale-input EV analyses had zero suggested stake.

These checks establish the implemented behavior and measured retrospective results. They do not establish profitable betting, fresh 2026 player state, comprehensive tournament coverage, or performance on a new blind future sample.

After the partial-2026 data extension, follow-up coverage checks returned 3 ATP and 9 WTA upcoming forecasts across those five reviewed tournaments. Names without sufficient history remain unavailable. WTA 125 forecasts have explicit unvalidated-level warnings and cannot pass EV admission. The legacy raw cleaner also stopped using full-dataset age/height averages; a regression test confirms that appending extreme future demographics cannot change earlier cleaned values. Changed surface provenance or tournament level creates a new append-only snapshot. Tennis-data.co.uk returned HTTP 403 during a further fresh-data/terms check; no alternative source was added without verification.

The committed completeness/suitability audit distinguishes eligible match outcomes from missing/invalid serving statistics and demographics. Valid serve-point observations require all three counts, finite nonnegative values, positive total points, and wins not exceeding the total. Partial or contradictory observations are skipped without fabricating zero wins. `python -m data.history_quality` re-verifies source checksums and writes a new timestamped report without replacing earlier reports.

## Subsequent GitHub verification and 2026 development

GitHub PR #1 and the remote preservation branch were verified at `9beaaf0` before further edits. GitHub's comparison confirms `69ece0b` is its ancestor with `78b8a18` and `9beaaf0` ahead; there was no current GitHub HTTP 403. No reset, discard, or recovery force-push was needed.

The existing pinned licensed mirrors contained 2,464 partial-2026 records despite earlier original-repository 404 checks. The extension verifies README hashes, schemas, file hashes, counts, exclusions, and identities while preserving prior files and manifests. New annual test-year training holds all 2026 labels out of fitting and deploys versioned models whose measured test period is shown accurately on the dashboard. WTA 125 row warnings are visible even when a main-tour row appears first.

The 2026 holdout scores 66.15% ATP (1,406 matches) and 66.25% WTA (957). Five yearly tests pool to 65.79% ATP (12,857) and 65.49% WTA (11,314). Paired date-block intervals on the same 2026 matches do not establish a clear improvement over the original frozen models. Full reports retain baselines, raw/calibrated scores, minimum-history coverage, date ranges, and limitations. Evaluation reports never activate a model.
