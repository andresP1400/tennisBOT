"""Refresh fixtures and log forecasts every five minutes while the API runs."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI

from api.personal_engine import PredictionCard, get_card
from api.personal_status import (
    POLL_SECONDS,
    begin_operation,
    finish_operation,
    set_running,
)
from pipeline.personal_settlement import settle_pending
from logging_config import get_logger

logger = get_logger(__name__)


async def refresh_predictions() -> None:
    """Failures are logged and retried later without manufacturing forecasts."""
    while True:
        await refresh_once()
        await asyncio.sleep(POLL_SECONDS)


async def refresh_once() -> None:
    """Failures in one phase/tour cannot suppress the remaining independent work."""
    for tour in ("atp", "wta"):
        await run_operation(tour, "predictions", lambda: get_card(tour, True))
        await run_operation(tour, "settlement", lambda: settle_pending(tour))


async def run_operation(tour: str, phase: str, operation: Callable[[], object]) -> None:
    """Record success only after the operation, including SQLite writes, completes."""
    begin_operation(tour, phase)
    try:
        result = await asyncio.to_thread(operation)
        if isinstance(result, PredictionCard) and result.model_version is None:
            raise FileNotFoundError("Trained personal model is missing")
        count = (
            len(result.predictions) if isinstance(result, PredictionCard) else result
        )
        finish_operation(tour, phase, count=count if isinstance(count, int) else None)
    except Exception as error:
        finish_operation(tour, phase, error_type=type(error).__name__)
        logger.exception("Personal %s refresh failed for %s", phase, tour)


@asynccontextmanager
async def personal_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the poller with the API lifecycle, preserving persisted tracking."""
    set_running(True)
    task = asyncio.create_task(refresh_predictions())
    try:
        yield
    finally:
        set_running(False)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
