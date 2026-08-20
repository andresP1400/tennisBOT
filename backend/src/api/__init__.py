"""FastAPI app package.

Exposes the ``app`` instance built by ``api_server`` so callers can target
``api.app`` (e.g. ``uvicorn api:app``) without creating an import cycle.

``api_server`` imports the route modules under ``api.routes``; since any
import of a subpackage runs this ``__init__`` first, we must NOT import
``api_server`` eagerly here. PEP 562 ``__getattr__`` resolves ``app`` lazily,
once ``api_server`` has finished loading.
"""
from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from api_server import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
