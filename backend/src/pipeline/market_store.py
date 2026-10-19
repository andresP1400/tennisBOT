"""Append-only private market observations and every qualifying strategy selection."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Literal, TypeVar

from pydantic import BaseModel

from pipeline.personal_tracking import TRACKING_DB, connect
from features.personal_schedule import Fixture

Table = Literal[
    "market_quotes", "betting_splits", "value_selections", "market_requests"
]
Record = TypeVar("Record", bound=BaseModel)
TABLES = ("market_quotes", "betting_splits", "value_selections", "market_requests")


def market_connect(path: Path | None = None) -> sqlite3.Connection:
    """Reuse the existing private durable database without changing old records."""
    database = connect(path or TRACKING_DB)
    for table in TABLES:
        database.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL,
            recorded_at TEXT NOT NULL, payload TEXT NOT NULL)""")
        database.execute(
            f"CREATE INDEX IF NOT EXISTS {table}_fixture ON {table}(fixture_id, recorded_at)"
        )
        for operation in ("UPDATE", "DELETE"):
            database.execute(
                f"""CREATE TRIGGER IF NOT EXISTS prohibit_{table}_{operation.lower()}
                BEFORE {operation} ON {table} BEGIN
                SELECT RAISE(ABORT, 'Market research records are append-only'); END"""
            )
    return database


def append_record(
    table: Table,
    record: BaseModel,
    fixture_id: str,
    path: Path | None = None,
    identity: str | None = None,
) -> str:
    """All observations get server-side record times and content identities."""
    if table not in TABLES:
        raise ValueError("Unsupported market table")
    payload = record.model_dump(mode="json", exclude={"id"})
    validate_observation(record)
    encoded = json.dumps(payload, sort_keys=True)
    identifier = hashlib.sha256((identity or encoded).encode()).hexdigest()
    database = market_connect(path)
    try:
        with database:
            database.execute(
                f"INSERT OR IGNORE INTO {table} VALUES (?, ?, ?, ?)",
                (
                    identifier,
                    fixture_id,
                    datetime.now(timezone.utc).isoformat(),
                    encoded,
                ),
            )
    finally:
        database.close()
    return identifier


def records(
    table: Table,
    model: type[Record],
    fixture_id: str | None = None,
    path: Path | None = None,
) -> list[Record]:
    """Read full private evidence for calculation; public endpoints paginate separately."""
    if table not in TABLES:
        raise ValueError("Unsupported market table")
    database = market_connect(path)
    try:
        where = " WHERE fixture_id = ?" if fixture_id else ""
        parameters = (fixture_id,) if fixture_id else ()
        rows = database.execute(
            f"SELECT id, payload FROM {table}{where} ORDER BY recorded_at", parameters
        ).fetchall()
        return [
            model.model_validate_json(payload).model_copy(update={"id": identifier})
            for identifier, payload in rows
        ]
    finally:
        database.close()


def validate_observation(record: BaseModel) -> None:
    """Server recording time prevents backdated post-match observations."""
    observed = getattr(record, "observed_at", None)
    if observed is not None and observed > datetime.now(timezone.utc):
        raise ValueError("Cannot record future observations")
    fixture = getattr(
        record, "fixture", getattr(getattr(record, "candidate", None), "fixture", None)
    )
    if (
        isinstance(fixture, Fixture)
        and datetime.now(timezone.utc) >= fixture.commence_time
    ):
        raise ValueError(
            "Cannot insert new market observations or selections after match start"
        )


def fixture_records(
    table: Table, model: type[Record], fixture_ids: list[str], path: Path | None = None
) -> dict[str, list[Record]]:
    """Read the bounded upcoming fixture set in one query instead of one per match."""
    if table not in TABLES:
        raise ValueError("Unsupported market table")
    grouped: dict[str, list[Record]] = {identifier: [] for identifier in fixture_ids}
    if not fixture_ids:
        return grouped
    database = market_connect(path)
    try:
        markers = ",".join("?" for _ in fixture_ids)
        rows = database.execute(
            f"SELECT id, fixture_id, payload FROM {table} WHERE fixture_id IN ({markers}) ORDER BY recorded_at",
            fixture_ids,
        ).fetchall()
        for identifier, fixture_id, payload in rows:
            grouped[fixture_id].append(
                model.model_validate_json(payload).model_copy(update={"id": identifier})
            )
        return grouped
    finally:
        database.close()
