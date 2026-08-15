# Security Notes

This file documents security-sensitive configuration and incident handling
for tennisBOT. Read it before deploying or after any secret exposure.

---

## ODDS_API_KEY rotation incident (June 2026)

The `ODDS_API_KEY` value (the first 4 + last 4 hex characters were
`9b49…f83`; the full value was committed in `.env` at the repository
root in v2.0).
The file is now listed in `.gitignore`, but the leaked key must be
treated as compromised even if the commit was reverted.

### What to do now

1. Sign in to https://the-odds-api.com and rotate the key
   (delete the old one, generate a fresh one).
2. Open `local.env` (created from `.env.example`) and paste the new key.
3. Make sure the new key is never committed.
4. Audit any logs that captured the old key (proxy, CDN, CI) and
   purge them.

### Verification

```bash
git log --all -p -- .env | head
# Should be empty once history has been purged (see "Hardening git
# history" below).
```

---

## Environment variable handling

* All secrets live in `local.env` (gitignored) on each developer machine
  and in the deployment platform's secret manager (Kubernetes secrets,
  GitHub Actions secrets, etc.).
* `.env.example` is the single source of truth for which keys exist and
  what format they expect.
* No secret should ever appear in:
  - source code
  - logs (the structured JSON logger redacts by name; do not log raw
    request headers / query strings)
  - query strings (TheOddsAPI rejects auth headers with 401
    `MISSING_KEY` — verified 2026-08-14 — so the key is passed as the
    `?apiKey=` query param; requests are HTTPS-only, never log the URL)
  - commit history

---

## API endpoint security posture

### `/api/predict` and `/api/value-bets`

`req.model` is matched against
`^(atp|wta)_(stacking_model|model|model_odds)\.pkl$` and the resolved path
is verified to live under `MODELS_DIR` via `Path.resolve()` plus
`startswith()`. Path traversal is rejected with HTTP 400.

### `/api/charts/[name]`

`name` is validated by `zod` to match `^[A-Za-z0-9_\-]+\.png$`. The
final path is checked with `path.resolve()` and a `startswith()` guard
against the `reports/` directory. Anything outside returns HTTP 403.

### CORS

`api_server.py` enables CORS for explicit origins
(`http://localhost:3000`, `http://127.0.0.1:3000`, ...) with
`allow_credentials=False`. Do not switch to `allow_origins=["*"]` without
also setting `allow_credentials=False`.

### Authentication

There is currently no auth layer (intentional for local dev). Before
exposing the API to a public network:

* Add a reverse proxy that requires a bearer token (nginx, Caddy, Traefik).
* Or add a FastAPI dependency that validates `Authorization: Bearer ...`
  against the local secrets store.

---

## Frontend security posture

* All chart image URLs go through the validated `/api/charts/[name]`
  route. There is no user-supplied file path on the client side.
* `<ThemeProvider>` is mounted in `layout.tsx`, so `useTheme()` in
  `sonner.tsx` and any future dark-mode UI works.
* `NEXT_PUBLIC_API_URL` overrides the backend base URL; never embed the
  backend URL directly in client code.
* Hardcoded `localhost:8000` references were removed in v2.1.

---

## Dependency hygiene

* `requirements.txt` is the runtime dependency list.
* `requirements-dev.txt` adds lint / type / test tooling.
* A CI workflow (`.github/workflows/ci.yml`) runs ruff + mypy + pytest on
  every push and PR.

---

## Reporting a vulnerability

If you find a new vulnerability in tennisBOT, please open a private
issue or contact the maintainers directly. Do not disclose publicly
until a fix is released.
