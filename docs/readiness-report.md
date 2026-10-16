# Daily personal-use readiness audit

Latest extension: [market research implementation and live/historical results](market-research.md). This earlier audit remains preserved as a dated checkpoint; the worker now exposes six phases.

Audit date: 2026-10-16 UTC. Scope: the personal ATP/WTA engine on the preservation branch, with the actual licensed files, trained model artifacts, public fixtures, and private prediction database. **This is a functioning personal research workflow, not a production-ready or proven reliable daily forecasting service.** No new model fitting or test-set tuning was performed for this audit.

## 1. Fully operational within the verified scope

| Workflow step | Real evidence | Practical limit |
| --- | --- | --- |
| Start backend and dashboard | The supervised `python start_all.py --production` starts both private loopback services, checks backend/dashboard HTTP readiness, and copies standalone assets. Browser/API checks pass. | Dependencies, production build and model artifacts must already exist. A liveness response alone does not validate forecasts. |
| Open and use the dashboard | Headless Chromium opened the real dashboard, switched ATP to WTA, and rendered 3 ATP and 7 WTA rows. Every rendered record ID matched the actual API. Historical-period, live-result and stale-history labels were present. | This browser check ran on Linux; the Mac setup is documented but has not been executed on a physical Mac. Counts change as fixtures start or draws are published. |
| Retrieve current fixtures | Public ESPN scoreboards provide a rolling seven-day singles schedule with named opponents, status and source timestamps. | One provider, no availability guarantee; unresolved draws, live/finished matches and starts outside the horizon are excluded. |
| Generate genuine forecasts | Both deployed local model artifacts load and their source fingerprints and evaluation reports match committed reports. Global/surface Elo and calibrated ML inference use real history. | Unknown/ambiguous players, fewer than ten prior completed matches, and unreviewed surfaces remain unavailable. |
| Save before display | SQLite commits each new forecast snapshot before returning it. Stored fields include both probabilities, model version, scheduled start, prediction time, provenance and any observed odds. | Persistence is local, not an external notarization or a guarantee against loss of the machine. |
| Preserve and read records | All 108 existing prediction payloads survived service restart without changes. SQLite integrity passed; append-only protections and idempotency are tested. | The file and model directory are private and intentionally absent from GitHub. |
| Evaluate completed forecasts | Eight actual stored outcomes have earlier pre-match forecasts. Fresh provider queries matched all eight recorded winners/statuses. Live scoring uses first forecasts and preserves old model results. | The audit rechecked already completed matches; it did not manufacture a new forecast for a finished match. Provider-corrected outcomes and long outages need further operational validation. |
| Run without sportsbook keys | Fixture retrieval, inference, recording and settlement succeed without sportsbook or LLM credentials. | No paired odds were available for the ten supported upcoming fixtures at this check. Missing odds remain null. |

The worker runs independently of browser access and attempts both predictions and settlement for both tours. `/api/personal/status` exposes process-local last-attempt, last-success, finish time, exception class and result count for each operation. It reports unhealthy after failures or missed cycles. Startup/reset status is not evidence of a completed cycle. `/api/health` remains only a liveness check.

The audit observed an actual second scheduled cycle five minutes after startup, with all four success timestamps advancing and no browser open. It found no newly completed tracked match in that interval; settlement correctly appended zero new outcomes. Existing eight outcomes were independently rechecked against fresh provider responses. A controlled frontend exit caused the supervisor to stop the sibling backend, free both ports and exit with an error; all 108 earlier forecast payloads remained unchanged.

## 2. Working features requiring further validation

| Area | Measured/verified behavior | What is not established |
| --- | --- | --- |
| ML accuracy | Available 2026 chronological holdout: ATP **66.15% / 1,406**; WTA **66.25% / 957**. Fits through 2023, selects on 2024, calibrates on 2025; no 2026 fitting labels. | Current October accuracy, profitability or a clear improvement over the original frozen models. |
| Runtime history-coverage subset | Requiring at least ten mature prior matches gives ATP **65.93% / 1,177** and WTA **66.24% / 862** in the historical test. | Exact provider-name matching and current tournament coverage impose additional live restrictions. |
| Prospective record | First-ever unique-fixture forecasts across all versions scored **2/8 correct** at the audit baseline: ATP 0/1, WTA 2/7. These poor results remain preserved. | Eight matches are too few for a stable accuracy estimate; retrospective scores must not be substituted for live results. |
| Probability calibration | Symmetric calibration ordering and chronological separation are tested; Brier/log-loss/calibration reports are retained. | Calibration under stale current player state, new tournaments, injuries or changing competition levels. |
| WTA 125 | Supported known-player forecasts carry a visible unvalidated-level warning and cannot pass EV calibration-provenance admission. | Main-tour historical accuracy does not validate WTA 125 performance. |
| Automatic updates and failure recovery | Worker success/error/missed-cycle monitoring and independent phase execution are tested. Browser refreshes have a 25-second deadline, clear old cards on error, and bypass caches. | Long-running uptime across laptop sleep, provider schema changes, offline periods and season changes. |
| Settlement | Exact fixture/tour/player identities, pre-start timestamps, bounded rescheduling and explicit provider final status are required. Retirements/walkovers/defaults are void. | Independent official verification, automatic correction of the first immutable result, complete recovery for provider-deleted or extensively rescheduled fixtures. |
| Expected-value analysis | Admission guards force zero stake for stale history, unvalidated levels, missing odds or insufficient independent books. No bets are placed. | The currently available inputs do not support actionable betting or measured returns. |

Detailed held-out methodology and the five annual test reports are in [the engine guide](personal-engine.md). Results were inspected during development and remain retrospective chronological evaluation, not a new blind experiment.

## 3. Missing integrations or credentials

- **Core engine:** no API key is missing. The public fixture/result endpoint and local model workflow already work.
- **Fresh historical results/player state:** no sufficiently current, reviewed and legally usable source has been integrated. A credential alone does not establish data rights or quality. Training on the same pinned files again will not make their contents current.
- **Broader fixtures/surfaces:** only eight reviewed 2026 tournament identities are registered. Additional ATP/WTA events and future seasons require verified surface/identity metadata. Some official ATP pages denied access; surfaces were not guessed.
- **Optional odds:** TheOddsAPI and Betfair bindings were absent in the audited runtime; LLM/research keys were also absent. They are optional, separate integrations. Existing scoreboard observations currently provide no paired odds for supported forecasts. Keys must be entered privately if these integrations are later enabled.
- **Access/uptime:** no remotely accessible private host, SSH endpoint, tunnel or always-on Mac service has been provisioned. The current cloud services bind to loopback. There is no remote dashboard URL to open from your Mac.
- **Off-machine record backup:** private archives exist in the cloud workspace, but an automatic off-machine backup destination is not configured. A Git clone restores source/provenance, not the private live record or model bytes. Mac backup and migration guidance is in [the daily-use instructions](mac-daily-use.md).

The legacy `/dashboard/predict`, training, player, analytics and track tools use a separate stacking pipeline and artifacts. The personal engine is the **Upcoming match predictions** panel on `/dashboard`, with `/api/personal/*` endpoints. Legacy metrics/models/track panels are explicitly labeled. The weekly GitHub Actions workflow does not automatically refresh or deploy the personal models or copy the local prediction database.

## 4. Critical blockers for dependable daily use

1. **Stale history and player statistics.** The reviewed snapshot contains 120,460 raw records in 44 checksum-verified files, with 115,975 eligible completed matches. ATP tournament starts end at **2026-05-25**, WTA at **2026-04-21**: respectively 144 and 178 days before the October 16 audit. Elo, rankings and form omit later results. The live outcome ledger does not automatically retrain or update model player summaries. Every current forecast warns about this gap.
2. **Incomplete coverage.** Only eight season/name/provider-verified tournament identities are supported. Seven additional current WTA fixtures were withheld: five for insufficient history and two for ambiguous/missing player coverage. Future draws can be TBD; new players and unreviewed events cannot receive trustworthy forecasts from the present state.
3. **No continuously available host/backup guarantee.** Closing the terminal, laptop sleep, cloud suspension or machine loss interrupts prediction recording. Restarting can attempt settlement of existing records, but cannot create a genuine pre-match forecast for a match missed while offline. Source pushed to GitHub does not protect private live records from machine loss.
4. **Current predictive quality remains unproven.** The measured historical tests pass their documented protocol, but the poor early live sample and stale state prevent a claim of dependable daily prediction quality. The workflow can be used to observe and collect research predictions while these limits are explicit.

## Audit fixes and verification

- Replaced the launcher's fixed startup sleep and unconditional success message with HTTP readiness checks, standalone production support, private binding, two-service supervision and owned-process cleanup. Occupied ports fail before starting duplicates. Ctrl-C/SIGTERM preserve all recorded data.
- Added inspectable poller status, failure isolation and missed-cycle detection. Missing model artifacts cannot count as a successful prediction update.
- Bounded browser requests and removed stale forecast cards on refresh failure. A delayed previous-tour response cannot replace the selected tour.
- Labeled legacy dashboard panels and replaced unreproduced README accuracy/market-return claims with linked, measured personal-model results. Earlier README content remains in Git history.
- Verified current source was already pushed at `3d44863` and the private Git/data/model/SQLite archive matched before making these audit changes. No reset, force-push, data replacement or historical record deletion was used.

Automated checks: **166 backend tests and 25 frontend tests**, strict mypy on 117 backend modules plus the launcher, Black/Ruff, TypeScript/ESLint, dependency consistency and production build. Real-data evidence includes deployed-model/report fingerprints, fresh outcome checks, actual Chromium dashboard rendering and unchanged private records after restart. The aggregate evidence file alongside this report records final runtime observations; it contains no match-level private prediction payloads. These are local checks: GitHub returned no check runs for the pre-audit commit, so a green remote CI run is not claimed.

Use [the Mac instructions](mac-daily-use.md) to run a private local instance. **The Mac commands are not evidence that installation has already succeeded on your hardware.** The cloud workflow has passed supported-fixture testing; stale history, limited coverage, uptime and backup limits remain open.
