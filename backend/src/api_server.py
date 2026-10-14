"""TennisBot FastAPI server (orchestrator).

Serves training status, live inference (tracker state), history, weather,
live odds, value bets, and certified prediction tracking.

All routes live in api/routes/*.py and are mounted here; this module only
owns the app instance, CORS, the env bootstrap and the dev entry point.
Module-level state (training status, caches) lives in api/state.py.
"""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import BASE_DIR, SRC_DIR, settings
from logging_config import get_logger

# Route modules (split out of the former 1260-line api_server.py).
from api.routes.analytics import router as analytics_router
from api.routes.card import router as card_router
from api.routes.data import router as data_router
from api.routes.models import router as models_router
from api.routes.players import router as players_router
from api.routes.predict import router as predict_router
from api.routes.system import router as system_router
from api.routes.track import router as track_router
from api.routes.training import router as training_router
from api.routes.personal import router as personal_router
from api.personal_worker import personal_lifespan

log = get_logger(__name__)

# .env first, then local.env (personal secrets override — legacy consumers
# and subprocesses still read os.environ; Settings reads the files itself).
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "local.env", override=True)

# API port (9090: outside Windows reserved/Hyper-V port ranges that block
# binds on 8000-8050 etc. with WSAEACCES)
API_PORT = settings.tennisbot_api_port

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    f"http://localhost:{API_PORT}",
    f"http://127.0.0.1:{API_PORT}",
]

app = FastAPI(
    lifespan=personal_lifespan,
    title="TennisBot API Engine",
    description=(
        "Backend ML/API per TennisBot. "
        "La UI web e' su http://localhost:3000 — qui trovi /docs e gli endpoint JSON."
    ),
    version="2.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

_ALLOWED_ORIGIN_SET = frozenset(ALLOWED_ORIGINS)


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):  # type: ignore[no-untyped-def]
    """CSRF guard for state-changing requests.

    CORS stops a malicious page from *reading* our responses, but the browser
    still *sends* the request — enough to trigger side effects (start training,
    invalidate caches). We reject any mutating request that carries a browser
    ``Origin`` not on the allow-list. Same-origin browser calls, the Next.js
    server-side proxy and CLI tools send no cross-origin ``Origin`` and pass.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin is not None and origin not in _ALLOWED_ORIGIN_SET:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site request blocked"},
            )
    return await call_next(request)


# --- Mount route modules on the app instance ---
for _router in (
    system_router,
    models_router,
    training_router,
    predict_router,
    players_router,
    track_router,
    data_router,
    analytics_router,
    card_router,
    personal_router,
):
    app.include_router(_router)

# Back-compat aliases for tests / scripts that imported internals from here.
from api.predict_core import resolve_model_path as _resolve_model_path  # noqa: E402
from api.state import load_dataset as _load_dataset  # noqa: E402
from api.state import training_status  # noqa: E402

__all__ = [
    "app",
    "API_PORT",
    "ALLOWED_ORIGINS",
    "BASE_DIR",
    "SRC_DIR",
    "training_status",
    "_resolve_model_path",
    "_load_dataset",
]


if __name__ == "__main__":
    import threading
    import uvicorn

    def _warmup() -> None:
        """Pre-fetch today's matches in the background so the dashboard
        never hits the 30s Next.js proxy timeout on first load."""
        try:
            from features.live_odds import LiveOddsScraper

            scraper = LiveOddsScraper()
            for tour in ("atp", "wta"):
                try:
                    scraper.get_todays_matches_cached(tour)
                except Exception as e:
                    log.warning("Warmup %s failed: %s", tour, e)
        except Exception as e:
            log.warning("Warmup failed: %s", e)

    log.info("TennisBot API listening on http://127.0.0.1:%s", API_PORT)
    threading.Thread(target=_warmup, name="warmup-matches", daemon=True).start()
    uvicorn.run("api_server:app", host="127.0.0.1", port=API_PORT, reload=False)
