"""Polling health must reflect failures, missed cycles, and recovery accurately."""

from datetime import datetime, timedelta, timezone, tzinfo
from collections.abc import Iterator

import pytest

from api import personal_status as status
from api import personal_worker as worker
from api.personal_engine import PredictionCard


@pytest.fixture(autouse=True)
def isolated_status() -> Iterator[None]:
    status.set_running(True)
    yield
    status.set_running(False)


@pytest.mark.asyncio
async def test_one_provider_failure_does_not_suppress_settlement_or_other_tour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def generate(tour: str, refresh: bool) -> PredictionCard:
        calls.append((tour, "predictions"))
        if tour == "atp":
            raise ConnectionError("provider unavailable")
        return PredictionCard(
            tour=tour, model_version="unit", fetched_at=datetime.now(timezone.utc)
        )

    def settle(tour: str) -> int:
        calls.append((tour, "settlement"))
        return 0

    monkeypatch.setattr(worker, "get_card", generate)
    monkeypatch.setattr(worker, "settle_pending", settle)
    monkeypatch.setattr(
        worker, "refresh_markets", lambda tour: calls.append((tour, "markets")) or 0
    )
    await worker.refresh_once()
    snapshot = status.worker_status()
    assert calls == [
        ("atp", "predictions"),
        ("atp", "settlement"),
        ("atp", "markets"),
        ("wta", "predictions"),
        ("wta", "settlement"),
        ("wta", "markets"),
    ]
    assert not snapshot["polling_healthy"]
    assert snapshot["operations"]["atp_predictions"]["error_type"] == "ConnectionError"
    assert snapshot["operations"]["wta_settlement"]["last_success"] is not None
    assert "provider unavailable" not in str(snapshot)


def test_polling_health_expires_after_missed_cycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(timezone.utc)
    for tour in ("atp", "wta"):
        for phase in ("predictions", "settlement", "markets"):
            status.begin_operation(tour, phase)
            status.finish_operation(tour, phase, count=0)
    assert status.worker_status()["polling_healthy"]

    class Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return now + timedelta(seconds=2 * status.POLL_SECONDS + 2)

    monkeypatch.setattr(status, "datetime", Clock)
    assert not status.worker_status()["polling_healthy"]
    status.set_running(False)
    assert not status.worker_status()["running"]


@pytest.mark.asyncio
async def test_successful_retry_preserves_then_clears_error() -> None:
    await worker.run_operation("atp", "predictions", lambda: 1 / 0)
    failed = status.worker_status()["operations"]["atp_predictions"]
    assert failed["error_type"] == "ZeroDivisionError"
    assert failed["last_success"] is None
    await worker.run_operation("atp", "predictions", lambda: 0)
    recovered = status.worker_status()["operations"]["atp_predictions"]
    assert recovered["error_type"] is None
    assert recovered["count"] == 0
    assert recovered["last_success"] is not None


@pytest.mark.asyncio
async def test_missing_model_cannot_report_successful_prediction_updates() -> None:
    await worker.run_operation(
        "atp",
        "predictions",
        lambda: PredictionCard(tour="atp", fetched_at=datetime.now(timezone.utc)),
    )
    operation = status.worker_status()["operations"]["atp_predictions"]
    assert operation["error_type"] == "FileNotFoundError"
    assert operation["last_success"] is None
