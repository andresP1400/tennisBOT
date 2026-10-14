"""Private append-only durable prediction events, independent of model refreshes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from config import REPORTS_DIR
from features.personal_schedule import Fixture

TRACKING_DB = REPORTS_DIR / "personal" / "prediction-events.sqlite3"


class Prediction(BaseModel):
    fixture: Fixture
    model_version: str
    model_family: str
    prob1: float = Field(ge=0, le=1)
    prob2: float = Field(ge=0, le=1)
    elo_prob1: float = Field(ge=0, le=1)
    winner: str
    predicted_at: datetime
    data_through: str
    history_age_days: int
    warning: str | None = None
    tracking_id: str | None = None

    @model_validator(mode="after")
    def validate_forecast(self) -> Prediction:
        """Stored snapshots must represent normalized pre-match probabilities."""
        if abs(self.prob1 + self.prob2 - 1) > 1e-8:
            raise ValueError("Win probabilities must sum to one")
        if (
            self.predicted_at.tzinfo is None
            or self.predicted_at >= self.fixture.commence_time
        ):
            raise ValueError(
                "Prediction timestamp must be timezone-aware and before match start"
            )
        return self


def connect(path: Path) -> sqlite3.Connection:
    """FULL synchronous commits plus immutable rows; personal local storage only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=30)
    path.chmod(0o600)
    database.execute("PRAGMA synchronous=FULL")
    database.execute("""CREATE TABLE IF NOT EXISTS prediction_events (
        id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, fixture_id TEXT NOT NULL,
        model_version TEXT NOT NULL, payload TEXT NOT NULL)""")
    for operation in ("UPDATE", "DELETE"):
        database.execute(f"""CREATE TRIGGER IF NOT EXISTS prohibit_{operation.lower()}
            BEFORE {operation} ON prediction_events BEGIN
            SELECT RAISE(ABORT, 'Prediction events are append-only'); END""")
    return database


def record_prediction(prediction: Prediction, path: Path | None = None) -> Prediction:
    """Commit before display; identical model/probability/odds snapshots are idempotent."""
    now = datetime.now(timezone.utc)
    if prediction.fixture.commence_time <= now:
        raise ValueError("Refusing to record a post-start prediction")
    payload = prediction.model_dump(mode="json", exclude={"tracking_id"})
    identity = {
        "fixture": prediction.fixture.id,
        "start": prediction.fixture.commence_time.isoformat(),
        "version": prediction.model_version,
        "prob1": prediction.prob1,
        "prob2": prediction.prob2,
        "odds1": prediction.fixture.odds1,
        "odds2": prediction.fixture.odds2,
        "odds_source": prediction.fixture.odds_source,
        "surface": prediction.fixture.surface,
    }
    identifier = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    database = connect(path or TRACKING_DB)
    try:
        with database:
            database.execute(
                "INSERT OR IGNORE INTO prediction_events VALUES (?, ?, ?, ?, ?)",
                (
                    identifier,
                    prediction.predicted_at.isoformat(),
                    prediction.fixture.id,
                    prediction.model_version,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        stored = database.execute(
            "SELECT payload FROM prediction_events WHERE id = ?", (identifier,)
        ).fetchone()
        if stored is None:
            raise RuntimeError("Prediction could not be durably recorded")
        return Prediction.model_validate_json(stored[0]).model_copy(
            update={"tracking_id": identifier}
        )
    finally:
        database.close()


def read_predictions(limit: int = 100, path: Path | None = None) -> list[Prediction]:
    """Return exact stored probabilities/timestamps, including odds at observation."""
    database = connect(path or TRACKING_DB)
    try:
        rows = database.execute(
            "SELECT id, payload FROM prediction_events ORDER BY observed_at DESC LIMIT ?",
            (min(1000, max(1, limit)),),
        ).fetchall()
        return [
            Prediction.model_validate_json(payload).model_copy(
                update={"tracking_id": identifier}
            )
            for identifier, payload in rows
        ]
    finally:
        database.close()
