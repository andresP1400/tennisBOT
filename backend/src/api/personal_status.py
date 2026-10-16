"""Inspectable process-local poller health; no credentials or forecast payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading

POLL_SECONDS = 300


@dataclass
class OperationStatus:
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    last_finished: datetime | None = None
    error_type: str | None = None
    count: int | None = None


_lock = threading.Lock()
_running = False
_operations: dict[tuple[str, str], OperationStatus] = {}


def set_running(running: bool) -> None:
    """A restored filesystem never implies that a polling process is alive."""
    global _running
    with _lock:
        _running = running
        if running:
            _operations.clear()


def begin_operation(tour: str, phase: str) -> None:
    """Track attempts separately from successful network/model/storage work."""
    with _lock:
        operation = _operations.setdefault((tour, phase), OperationStatus())
        operation.last_attempt = datetime.now(timezone.utc)


def finish_operation(
    tour: str, phase: str, *, count: int | None = None, error_type: str | None = None
) -> None:
    """Expose exception classes only, avoiding provider details or secret values."""
    with _lock:
        operation = _operations.setdefault((tour, phase), OperationStatus())
        operation.last_finished = datetime.now(timezone.utc)
        operation.error_type, operation.count = error_type, count
        if error_type is None:
            operation.last_success = operation.last_finished


def worker_status() -> dict[str, object]:
    """Healthy polling does not imply fresh historical inputs or validated accuracy."""
    now = datetime.now(timezone.utc)
    with _lock:
        operations = {
            f"{tour}_{phase}": _operations.get((tour, phase), OperationStatus())
            for tour in ("atp", "wta")
            for phase in ("predictions", "settlement")
        }
        healthy = _running and all(
            operation.last_success is not None
            and operation.error_type is None
            and (now - operation.last_success).total_seconds() <= 2 * POLL_SECONDS
            for operation in operations.values()
        )
        return {
            "running": _running,
            "polling_healthy": healthy,
            "interval_seconds": POLL_SECONDS,
            "checked_at": now,
            "operations": {name: asdict(value) for name, value in operations.items()},
        }
