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
python -m pipeline.personal_train --tour both
```

On a fresh machine, create a virtual environment and install `requirements.txt` and `requirements-dev.txt` first. To use the measured model-library versions, run `pip install -r requirements.txt -r requirements-dev.txt -c docs/model-validation/constraints.txt`. The downloader restores exactly the reviewed files and refuses conflicting existing files. See [data provenance and license](data-sources/README.md). The data is licensed **CC BY-NC-SA 4.0**, attributed to Jeff Sackmann / Tennis Abstract, and is used here for personal noncommercial research.

Each training run creates new versioned model and audit files under `models/saved/personal/` and `reports/personal/{tour}/`. Earlier versions are retained. Only the active-version pointer is replaced after saving the new artifact. These files are local and ignored by Git. Re-running training twice produced identical measured accuracy, Brier scores, and log-loss with the installed libraries.

## What was measured

All 117,996 raw rows were verified against committed SHA-256 checksums. The audit excluded 2,277 ATP and 2,107 WTA rows for incomplete/retired/walkover/defaulted matches, unknown surfaces, or invalid/duplicate metadata (exclusion categories can overlap). No duplicate match identities were found. The usable totals are 59,169 ATP and 54,443 WTA matches.

The source contains all 42 expected annual files. This establishes completeness against the pinned snapshot, not coverage of every match played worldwide. In particular it does not contain 2026 results. Each version's audit records annual counts and source revisions.

Chronological protocol:

- 2005–2007: rating/history warmup.
- 2008–2021: estimator fitting and training-only scaling.
- 2022: select logistic regression or histogram gradient boosting by log-loss.
- 2023: fit symmetric Platt calibration; never fit calibration on the test years.
- 2024–2025: held-out evaluation, one row per match. Estimators and calibration stay frozen, while player summaries update forward only as historical results become available.

Because source dates identify tournament starts rather than exact match times, every date batch freezes all features before any result in that batch is applied. This deliberately avoids optimistic within-week ordering assumptions. Player-order augmentation is used only for training; mirror rows are not counted as independent test matches. Prediction probabilities are symmetric when players are reversed.

| Tour | Selected ML family | Test matches | Calibrated ML accuracy | Brier | Log-loss | ROC-AUC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ATP | Histogram gradient boosting | 5,786 | 65.45% | 0.2129 | 0.6126 | 0.7195 |
| WTA | Logistic regression | 5,169 | 65.74% | 0.2150 | 0.6191 | 0.7160 |

The committed [validation reports](model-validation/) include surface-Elo baselines, uncalibrated results, calibration error, yearly and surface breakdowns, sample counts, and audit metadata. Calibration is fitted honestly; it is not guaranteed to improve future scores. In this evaluation WTA calibration slightly worsened held-out Brier/log-loss. No betting profitability or live accuracy is claimed. No test-driven model optimization was performed after observing these results.

## Run and inspect forecasts

```bash
python -m uvicorn api_server:app --app-dir backend/src --host 127.0.0.1 --port 9090
# In another terminal:
cd frontend
npm ci
npm run build
npm run start -- --hostname 127.0.0.1
```

The dashboard's “Upcoming match predictions” panel displays each supported fixture, predicted winner, estimated winning probability, recorded timestamp, model version, and observed odds where available. The model was trained on real outcomes; the displayed historical accuracy is explicitly separated from live performance.

The API polls ESPN's public ATP/WTA scoreboards every five minutes, records predictions, and continues retrying after provider failures. Dashboard requests share a five-minute cache. Completed/live matches, doubles, past starts, and unresolved competitors are excluded. Unknown or ambiguously matched players and players with fewer than ten historical completed matches are left unavailable. Names are normalized for accents and punctuation without speculative fuzzy matching.

Surface verification currently covers Shanghai ATP and Wuhan WTA by known provider tournament identity. Other tournament surfaces are deliberately left unverified, so those fixtures have no prediction. Extend the reviewed registry as new tournaments become relevant. Providers may omit fixtures or change their schemas; public endpoint access is not a blanket redistribution license. This is a local personal-use workflow, not a comprehensive licensed commercial fixture feed.

The latest history ends in 2025. Current forecasts therefore omit 2026 results/rankings and carry explicit data-age warnings. They demonstrate functioning inference but cannot be assumed to match the historical backtest's quality. Licensed fresh match data and additional verified surfaces are the main remaining coverage improvements. No credential is currently required for the supported workflow.

## Private pre-match tracking

Every forecast is committed before being returned to the dashboard. `reports/personal/prediction-events.sqlite3` stores the fixture identity, scheduled start, UTC prediction time, model version, both win probabilities, Elo probability, data-through date, and any available real market prices, provider, and observation time. Missing odds remain null; provider moneylines are converted to decimal prices in player order. The core engine does not make sportsbook API calls.

Snapshots are append-only: database triggers reject updates and deletions. Changed model versions, prices, probabilities, or scheduled starts create new records. Identical snapshots reuse the first record and timestamp. Writes are transactionally committed with SQLite FULL synchronous mode; the file is readable only by its owner. Old snapshots remain available after restart or retraining. The API never logs forecasts after a match's scheduled start.

This is private local persistence, not an external notarization or a guarantee against deletion of the machine. Back up the database using SQLite's backup API and retain the versioned model directory if moving environments. Do not commit the database, datasets, or model artifacts to a public repository. Live processes and periodic polling must restart after restoring an environment snapshot.

Endpoints:

- `GET /api/personal/predictions?tour=atp` (or `wta`): recorded upcoming forecasts and honest availability reasons.
- `GET /api/personal/backtest?tour=atp`: measured results for the deployed model.
- `GET /api/personal/history?limit=100`: exact historical prediction snapshots.

Both services bind to loopback for personal use. No web preview, public deployment, credentials, or outbound messages are created by this setup.
