"""Timestamped paired prices and optional public observations, never synthetic inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from features.personal_schedule import Fixture
from pipeline.personal_state import normalize_name


class QuoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    fixture: Fixture
    bookmaker: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_\-]+$")
    odds1: float = Field(gt=1, le=1000)
    odds2: float = Field(gt=1, le=1000)
    quoted_at: datetime | None = None
    kind: Literal["current", "opening", "closing"] = "current"
    commission: float | None = Field(default=0, ge=0, lt=1)
    source_url: str | None = Field(default=None, max_length=500)


class MarketQuote(QuoteInput):
    observed_at: datetime
    provenance: Literal["manual", "espn_observation", "theoddsapi"]
    provider_event_id: str | None = None
    id: str | None = None

    @model_validator(mode="after")
    def timing_and_players(self) -> MarketQuote:
        times = [self.fixture.commence_time, self.observed_at]
        if self.quoted_at is not None:
            times.append(self.quoted_at)
        if any(value.tzinfo is None for value in times):
            raise ValueError("Market timestamps must be timezone-aware")
        if not self.observed_at < self.fixture.commence_time:
            raise ValueError(
                "Only actually observed pre-match prices may enter this ledger"
            )
        if self.quoted_at is not None and self.quoted_at > self.observed_at:
            raise ValueError("Provider quote cannot be newer than its observation")
        if normalize_name(self.fixture.player1) == normalize_name(self.fixture.player2):
            raise ValueError("Market requires two distinct opponents")
        return self


class SplitInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    fixture: Fixture
    source: str = Field(min_length=1, max_length=150)
    scope: str = Field(min_length=1, max_length=300)
    published_at: datetime
    tickets1: float = Field(ge=0, le=100)
    tickets2: float = Field(ge=0, le=100)
    money1: float | None = Field(default=None, ge=0, le=100)
    money2: float | None = Field(default=None, ge=0, le=100)
    sample_size: int | None = Field(default=None, gt=0)


class BettingSplit(SplitInput):
    observed_at: datetime
    provenance: Literal["manual", "authorized_provider"]
    id: str | None = None

    @model_validator(mode="after")
    def valid_distribution(self) -> BettingSplit:
        if abs(self.tickets1 + self.tickets2 - 100) > 0.01:
            raise ValueError("Ticket shares must sum to 100")
        if (self.money1 is None) != (self.money2 is None):
            raise ValueError("Money shares require both sides or neither")
        if self.money1 is not None and self.money2 is not None:
            if abs(self.money1 + self.money2 - 100) > 0.01:
                raise ValueError("Money shares must sum to 100")
        times = [self.published_at, self.observed_at, self.fixture.commence_time]
        if any(value.tzinfo is None for value in times):
            raise ValueError("Split timestamps must be timezone-aware")
        if not self.published_at <= self.observed_at < self.fixture.commence_time:
            raise ValueError("Split publication/observation must precede the match")
        return self


class ProbabilityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    model_version: str
    estimated_probability: float = Field(gt=0, lt=1)
    lower_probability: float = Field(ge=0, le=1)
    upper_probability: float = Field(ge=0, le=1)
    matches: int = Field(ge=100)
    date_blocks: int = Field(ge=20)
    method: str = Field(min_length=1)
    validation_end: datetime
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def ordered_bounds(self) -> ProbabilityEvidence:
        if (
            not self.lower_probability
            <= self.estimated_probability
            <= self.upper_probability
        ):
            raise ValueError("Evidence bounds must contain the model estimate")
        if self.validation_end.tzinfo is None:
            raise ValueError("Validation time must be timezone-aware")
        return self
