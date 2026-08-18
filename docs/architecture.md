# Architecture

This document describes the repository layout introduced with the
AGENT.md-driven restructure. All existing functionality is preserved: only
file locations and path anchors changed.

## Repository layout

```
tennisBOT-main/
├── AGENT.md                  # project rules (changelog, structure, naming, tooling)
├── CHANGELOG.md              # mandatory, updated before every merge
├── README.md
├── start_all.py              # launcher: backend API + frontend dev server
├── requirements.txt / requirements-dev.txt
├── mypy.ini
├── .env.example              # template ONLY - real secrets live in local.env (gitignored)
│
├── backend/
│   ├── src/                  # import root (python -m / cwd entry points)
│   │   ├── api_server.py     # FastAPI app (predict, predict-card, value-bets, ...)
│   │   ├── main.py           # CLI orchestrator (download/features/train/refresh/settle)
│   │   ├── config.py         # all paths + hyperparameters (_PROJECT_ROOT = repo root)
│   │   ├── logging_config.py
│   │   ├── exceptions.py
│   │   ├── smoke_test.py / smoke_train.py
│   │   ├── features/         # feature engineering + external odds/volume services
│   │   ├── pipeline/         # training, evaluation, inference, tracking
│   │   ├── data/             # raw data download (data/download.py)
│   │   └── utils/            # shared constants
│   └── tests/                # pytest suite (mirrors src layout expectations)
│
├── frontend/                 # Next.js 16 dashboard (App Router, TypeScript)
│   └── src/
│       ├── app/              # routes (dashboard pages + /api proxy rewrites)
│       ├── components/       # UI components (shadcn/ui based)
│       ├── lib/              # api client, feature catalogue
│       └── hooks/ (if added) # one hook per domain
│
├── docs/                     # architecture.md, SECURITY.md, DATA_SOURCES.md
├── scripts/                  # security scan, refresh helper, one-shot utilities
├── data/                     # raw + processed artifacts (gitignored)
├── models/saved/             # trained .pkl bundles (gitignored)
└── reports/                  # metrics, charts, prediction tracking (gitignored)
```

## Path anchoring rules

- `backend/src/config.py` defines `_PROJECT_ROOT` as the repository root
  (three levels up from the file) and derives `PROCESSED_DIR`, `RAW_DIR`,
  `MODELS_DIR`, `REPORTS_DIR` from it. All pipeline code imports paths from
  `config` - never hardcode `data/...` relative paths in modules.
- `backend/src/api_server.py` distinguishes `SRC_DIR` (where `main.py` and
  sources live, used as training subprocess cwd) from `BASE_DIR` (repo root,
  used for `.env`/`local.env` and datasets).
- Modules inside `backend/src/features/` and `backend/src/pipeline/` keep the
  legacy `sys.path.insert(0, dirname(dirname(__file__)))` bootstrap which now
  resolves to `backend/src` - imports like `from features.odds import ...`
  are unchanged.
- `.env` / `local.env` are loaded from the repository root only.

## Entry points

| Action | Command (from repo root) |
| :--- | :--- |
| Full stack (API + dashboard) | `python start_all.py` |
| API only | `python backend/src/api_server.py` |
| CLI pipeline | `python backend/src/main.py <download/features/train/refresh/settle/all>` |
| Tests | `python -m pytest backend/tests -q` |
| Type check | `cd backend/src && mypy --config-file ../../mypy.ini .` |
| Frontend dev | `cd frontend && npm run dev` |

CI (`.github/workflows/ci.yml`) and the scheduled Weekly Refresh use the same
paths; mypy runs with `working-directory: backend/src` so the per-module
sections in `mypy.ini` (`[mypy-features.elo]`, ...) keep matching.

## Data flow

1. **Download** (`backend/src/data/download.py`) - pulls ATP/WTA match
   archives from the mirror repo into `data/raw/`.
2. **Features** (`backend/src/features/builder.py`) - builds the feature
   parquet in `data/processed/` and serializes the tracker inference state.
3. **Training** (`backend/src/pipeline/training.py`) - stacking ensemble,
   saves bundles to `models/saved/`, metrics to `reports/`.
4. **Serving** (`backend/src/api_server.py`) - live inference from the
   tracker state, live odds via TheOddsAPI/SofaScore aggregation, automatic
   daily card (`/api/predict-card`), value-bet detection.
5. **Dashboard** (`frontend/`) - Next.js UI proxying `/api/*` to FastAPI.
6. **Weekly Refresh** (GitHub Actions) - re-runs steps 1-3 for both tours
   every Monday and uploads artifacts.
