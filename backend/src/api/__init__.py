"""FastAPI app package.

Re-exports the FastAPI ``app`` instance built by ``api_server`` so callers
(e.g. ``start_all.py``, ``uvicorn api:app``) can target the package name
without pulling in the module-level globals of ``api_server``.

A subsequent refactor will split the 1200+ line ``api_server`` into a
``routes/`` subpackage; the entry point stays the same (``api.app``).
"""
from __future__ import annotations

from api_server import app  # noqa: F401

__all__ = ["app"]
