# Open TennisBOT on your Mac

The running Codex application is inside a cloud machine. Typing `localhost:3000` on your Mac reaches your Mac, not that cloud machine. No private remote URL or SSH/tunnel access has been configured. The concrete available route is to run the checked-in application locally on your Mac.

These steps use Terminal, Homebrew, Python 3.12, Node 24, and the preservation branch. The same production workflow was tested on Linux; installation on your physical Mac remains unverified. Read [the readiness limits](readiness-report.md), especially the stale 2026 data, before using its probabilities.

## First installation

If Homebrew is not installed, install it using its official instructions at https://brew.sh first. Then open **Applications → Utilities → Terminal** and run:

```bash
brew install python@3.12 node@24 libomp
export PATH="$(brew --prefix node@24)/bin:$PATH"
git clone --branch codex/preserve-verified-tennisbot https://github.com/andresP1400/tennisBOT.git "$HOME/TennisBOT-daily"
cd "$HOME/TennisBOT-daily"
"$(brew --prefix python@3.12)/bin/python3.12" -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt -c docs/model-validation/constraints.txt
python -m pip check
```

The clone command deliberately fails if `TennisBOT-daily` already exists; it does not overwrite it. If GitHub authentication is required, use your existing private GitHub access. No sportsbook or LLM keys are required, and no key belongs in chat or committed files. `libomp` supplies OpenMP for the repository's native ML dependencies on macOS.

Download the exact reviewed licensed history and train both real models:

```bash
export PYTHONPATH="$PWD/backend/src"
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
python -m data.licensed_history --tour both
python -m data.history_quality
python -m pipeline.personal_train --tour both --test-year 2026
```

Training can take several minutes. Each successful tour run creates a versioned artifact and active pointer under `models/saved/personal/`. Do not skip training on a fresh Git clone: model bytes are intentionally private and are not in Git. The downloaded history remains partial through May ATP / April WTA; this command does not acquire missing later results. A checksum conflict preserves your existing file and stops instead of replacing it.

Build the dashboard, with the proxy explicitly pointing at the private local backend:

```bash
cd frontend
npm ci
unset NEXT_PUBLIC_API_URL
BACKEND_URL=http://127.0.0.1:9090 NEXT_TELEMETRY_DISABLED=1 npm run build
cd ..
python start_all.py --production
```

Wait for `Dashboard ready on this machine` in the terminal. The launcher copies standalone static/public assets, checks service readiness, and binds both services to loopback. Do not use `npm start` for the configured standalone output. If ports 3000/9090 are occupied, stop your previous TennisBOT instance with Ctrl-C; the launcher will not kill or reuse an unrelated listener.

Open a **second Terminal window** and run:

```bash
open 'http://127.0.0.1:3000/dashboard'
```

In the **Upcoming match predictions** panel, select ATP or WTA. It shows supported upcoming matches, predicted winner, win probability, data-age warning, historical metrics and live results. Expand **Recorded forecast** to see the stored timestamp, model version and record ID. Unsupported fixtures have an explanation. Other legacy prediction/training/track pages use separate artifacts and do not represent this personal record.

## Start on later days

After the first installation/build/training, use:

```bash
cd "$HOME/TennisBOT-daily"
export PATH="$(brew --prefix node@24)/bin:$PATH"
source .venv/bin/activate
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
caffeinate -i python start_all.py --production
```

Then run `open 'http://127.0.0.1:3000/dashboard'` in another Terminal. Leave the first terminal running. `caffeinate -i` prevents idle sleep while the command runs; closing the lid, logout, reboot or closing Terminal can still interrupt work. This is not a boot-time/always-on service. Ctrl-C stops the application and retains records.

The backend polls every five minutes even with no browser open; the dashboard refreshes every minute. Provider/network/processing time adds to those intervals. It records before displaying, keeps identical forecast snapshots idempotent, and attempts automatic settlement after provider-confirmed completion. Missed offline matches cannot be predicted retrospectively.

To distinguish successful updates from a merely running API, use the activated environment in a second Terminal:

```bash
curl -fsS 'http://127.0.0.1:3000/api/personal/status' | python -m json.tool
curl -fsS 'http://127.0.0.1:3000/api/personal/live-performance?tour=atp&scope=all' | python -m json.tool
curl -fsS 'http://127.0.0.1:3000/api/personal/live-performance?tour=wta&scope=all' | python -m json.tool
```

After a completed cycle, expect `running: true`, `polling_healthy: true`, and recent `last_success` times for all four operations. Zero newly settled outcomes is normal when no pending match has finished. Unhealthy/stale status needs investigation even when `/api/health` returns OK. Healthy polling does not make stale player history current.

## Keep private records safe

Predictions and outcomes are in `reports/personal/prediction-events.sqlite3`; all model versions are in `models/saved/personal/`. Neither is pushed to GitHub. A fresh Mac installation starts a separate local record; it does **not** automatically include the cloud's existing predictions. For continuity, securely transfer a consistent cloud database backup and its model artifacts before starting a new local record. If local records already exist, preserve them separately and do not overwrite either database. No cross-database merge or private file-transfer service has been provisioned.

From the activated environment at the repository root, make a consistent versioned database backup while the app is running:

```bash
python - <<'PY'
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

os.umask(0o077)
folder = Path.home() / "TennisBOT-backups"
folder.mkdir(mode=0o700, exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
target = folder / f"prediction-events-{stamp}.sqlite3"
source = Path("reports/personal/prediction-events.sqlite3").resolve()
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as database:
    with sqlite3.connect(target) as backup:
        database.backup(backup)
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
print(target)
PY
```

Include this backup directory and the versioned model directory in a private off-machine backup such as your own Time Machine disk. Local copies alone do not survive loss of the Mac/cloud machine. Do not publish database files, raw history, model bytes, `.env` files or private archives to the repository.

## After source changes

Stop the application before rebuilding its shared `.next` directory. Preserve local changes before fetching/checking out updates; do not reset your checkout to follow this guide. Re-run dependency installation only when requirements/lockfiles change, and run `npm ci` plus the production build when frontend code changes. Restart the launcher afterward. Retraining creates a new version and retains old results; do not retrain just to hide a bad live record.

If installation fails, retain the exact command/error, check Python/Node versions and `python -m pip check`, and fix that prerequisite. Do not substitute generated predictions, bypass license/checksum verification or assume missing odds are even-money prices.
