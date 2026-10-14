"""Refresh fixtures and log forecasts every five minutes while the API runs."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator

from fastapi import FastAPI

from api.personal_engine import get_card
from logging_config import get_logger

logger = get_logger(__name__)


async def refresh_predictions() -> None:
    """Failures are logged and retried later without manufacturing forecasts."""
    while True:
        for tour in ("atp", "wta"):
            try:
                await asyncio.to_thread(get_card, tour, True)
            except Exception:
                logger.exception("Personal prediction refresh failed for %s", tour)
        await asyncio.sleep(300)


@asynccontextmanager
async def personal_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the poller with the API lifecycle, preserving persisted tracking."""
    task = asyncio.create_task(refresh_predictions())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
