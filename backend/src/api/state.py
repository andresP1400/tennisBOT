"""Shared mutable state used by the API routers.

Centralises the state dicts that used to live as module-level globals in
``api_server``. Routers read and mutate them through ``request.app.state``
so each test or subprocess starts from a clean slate.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def make_app() -> FastAPI:
    """Construct the FastAPI app with CORS middleware and state defaults."""
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="TennisBot API", version="1.0")
    app.state.training_status: dict[str, Any] = {
        "is_training": False,
        "current_task": "Idle",
        "progress": 0,
        "logs": [],
        "error": False,
        "success": False,
    }
    app.state.global_dataset: Any = None
    app.state.global_dataset_mtime: float = 0.0
    app.state.global_dataset_tour: str = ""
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:9090",
        "http://127.0.0.1:9090",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
