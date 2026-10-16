"""Exact provider fixture outcomes, never guessed from player names or rankings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, model_validator

from features.personal_schedule import Competition, Scoreboard


class MatchOutcome(BaseModel):
    fixture_id: str
    tour: str
    player1: str
    player2: str
    winner: str | None
    status: Literal["completed", "void"]
    scheduled_start: datetime
    observed_at: datetime
    source: str = "ESPN public scoreboard"

    @model_validator(mode="after")
    def validate_result(self) -> MatchOutcome:
        """Reject internally inconsistent or un-timestamped result observations."""
        if self.scheduled_start.tzinfo is None or self.observed_at.tzinfo is None:
            raise ValueError("Result timestamps must be timezone-aware")
        if self.scheduled_start > self.observed_at:
            raise ValueError("Results cannot precede their scheduled start")
        if self.status == "completed" and self.winner not in {
            self.player1,
            self.player2,
        }:
            raise ValueError(
                "Completed results require one of the named players as winner"
            )
        if self.status == "void" and self.winner is not None:
            raise ValueError("Voided matches do not count toward win accuracy")
        return self


def parse_outcomes(
    board: Scoreboard, tour: str, observed: datetime
) -> list[MatchOutcome]:
    """Only final completed singles count; retirements/defaults are recorded as void."""
    slug = "mens-singles" if tour == "atp" else "womens-singles"
    outcomes = []
    for event in board.events:
        for group in event.groupings:
            if group.grouping.slug != slug:
                continue
            for match in group.competitions:
                outcome = outcome_from_match(match, tour, observed)
                if outcome is not None:
                    outcomes.append(outcome)
    return outcomes


def outcome_from_match(
    match: Competition, tour: str, observed: datetime
) -> MatchOutcome | None:
    """Require explicit completion and an unambiguous winner before scoring."""
    status = match.status.type
    names = [item.athlete.displayName.strip() for item in match.competitors]
    winners = [
        item.athlete.displayName.strip() for item in match.competitors if item.winner
    ]
    if (
        status.state != "post"
        or not status.completed
        or len(names) != 2
        or match.date > datetime.now(timezone.utc)
        or not all(names)
    ):
        return None
    state: Literal["completed", "void"]
    if status.name == "STATUS_FINAL" and len(winners) == 1:
        winner, state = winners[0], "completed"
    elif status.name in {
        "STATUS_RETIRED",
        "STATUS_WALKOVER",
        "STATUS_CANCELED",
        "STATUS_DEFAULTED",
    }:
        winner, state = None, "void"
    else:
        return None
    return MatchOutcome(
        fixture_id=f"espn:{tour}:{match.id}",
        tour=tour,
        player1=names[0],
        player2=names[1],
        winner=winner,
        status=state,
        scheduled_start=match.date,
        observed_at=observed,
    )
