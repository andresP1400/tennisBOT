"""FastAPI route modules grouped by domain.

Each module exposes a ``router`` (APIRouter) that the app assembles in
``api.app``. Keep the routers small and independent so they can be split
further when a file crosses the 300-line limit.
"""
from __future__ import annotations

__all__: list[str] = []