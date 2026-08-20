"""System routes: root landing page, liveness probe, odds API health check."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from config import BASE_DIR

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def root_landing() -> str:
    """Friendly landing page — browsers hit / and used to see a blank/black 404."""
    return """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TennisBot API</title>
  <style>
    :root { color-scheme: dark; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
      background: #0b1220; color: #e8eefc;
    }
    .card {
      width: min(520px, 92vw); padding: 2rem; border-radius: 16px;
      background: #121a2b; border: 1px solid #243049; box-shadow: 0 20px 50px #0008;
    }
    h1 { margin: 0 0 .5rem; font-size: 1.6rem; }
    p { margin: 0 0 1.25rem; color: #9fb0d0; line-height: 1.5; }
    a.btn {
      display: inline-block; margin: .35rem .5rem .35rem 0; padding: .7rem 1rem;
      border-radius: 10px; text-decoration: none; font-weight: 600;
    }
    .primary { background: #10b981; color: #042f1f; }
    .secondary { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }
    code { color: #86efac; }
    ul { margin: 0 0 1rem 1.1rem; color: #9fb0d0; }
  </style>
</head>
<body>
  <div class="card">
    <h1>TennisBot API</h1>
    <p>
      Questa e' l'API backend (JSON). La pagina nera/vuota che vedevi era un 404 sulla root.
      Per usare la piattaforma di predizione apri la dashboard Next.js.
    </p>
    <a class="btn primary" href="http://localhost:3000/dashboard/predict">Apri Predict UI</a>
    <a class="btn secondary" href="http://localhost:3000/dashboard">Dashboard</a>
    <a class="btn secondary" href="/docs">API Docs (Swagger)</a>
    <a class="btn secondary" href="/api/status">/api/status</a>
    <p style="margin-top:1.25rem;font-size:.9rem">
      Endpoint utili: <code>/api/predict</code>, <code>/api/models</code>,
      <code>/api/track</code>, <code>/api/history</code>
    </p>
  </div>
</body>
</html>"""


@router.get("/health", include_in_schema=False)
@router.get("/api/health")
def health() -> dict:
    """Simple liveness probe for monitors and reverse proxies."""
    return {"status": "ok", "service": "tennisbot-api"}


@router.get("/api/odds-api-status")
def check_odds_api_status() -> dict:
    """Check if TheOddsAPI key is configured and working."""
    api_key = os.environ.get("ODDS_API_KEY", "").strip()
    env_path = BASE_DIR / ".env"
    local_path = BASE_DIR / "local.env"
    preferred = str(local_path if local_path.is_file() else env_path)
    if not api_key or api_key == "your_api_key_here":
        return _missing_key_payload(env_path, local_path, preferred)
    try:
        import requests
        url = "https://api.the-odds-api.com/v4/sports/"
        resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
        if resp.status_code == 200:
            sports = resp.json()
            tennis = [s for s in sports if s.get("key", "").startswith("tennis_")]
            return {
                "configured": True,
                "status": "OK",
                "remaining_requests": resp.headers.get("x-requests-remaining", "unknown"),
                "tennis_tournaments": len(tennis),
                "tennis_keys": [s["key"] for s in tennis[:10]],
            }
        return {
            "configured": True,
            "status": f"Error {resp.status_code}",
            "message": "API key may be invalid or expired",
        }
    except Exception as e:
        return {"configured": True, "status": "Error", "message": str(e)}


def _missing_key_payload(env_path: Path, local_path: Path, preferred: str) -> dict:
    """Standardised response shown when ODDS_API_KEY is unset or placeholder."""
    return {
        "configured": False,
        "message": (
            "ODDS_API_KEY not set. Edit local.env (or .env) in the project root "
            "with your key from https://the-odds-api.com, then restart the API."
        ),
        "how_to_get": (
            "1) Go to https://the-odds-api.com  2) Sign up free  "
            "3) Copy your API key  4) Paste in local.env as ODDS_API_KEY=your_key  "
            "5) Restart: python api_server.py"
        ),
        "free_tier": "500 requests/month",
        "env_file": preferred,
        "env_candidates": [str(env_path), str(local_path)],
    }
