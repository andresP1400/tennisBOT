"""Reviewed season-specific surfaces with explicit cross-provider identities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache


@dataclass(frozen=True)
class SurfaceReview:
    surface: str
    names: tuple[str, ...]
    source: str
    level: str | None = None
    venue: str | None = None
    start_date: date | None = None
    end_date: date | None = None


WTA_CALENDAR = "https://api.wtatennis.com/tennis/tournaments/?page=0&pageSize=100&from=2026-10-01&to=2026-10-31"

# ESPN identifiers differ from WTA's; names and season must also agree.
REVIEWS = {
    ("atp", "708", "2026"): SurfaceReview(
        "Hard",
        ("Almaty Open",),
        "https://www.protennislive.com/posting/2026/9410/mds.pdf",
        "ATP 250",
        "Almaty, Kazakhstan",
        date(2026, 10, 17),
        date(2026, 10, 25),
    ),
    ("atp", "440", "2026"): SurfaceReview(
        "Hard",
        ("BNP Paribas Fortis European Open",),
        "https://www.protennislive.com/posting/2026/7485/mds.pdf",
        "ATP 250",
        "Brussels, Belgium",
        date(2026, 10, 17),
        date(2026, 10, 25),
    ),
    ("atp", "315", "2026"): SurfaceReview(
        "Hard",
        ("Rolex Shanghai Masters", "Shanghai"),
        "https://www.atptour.com/en/tournaments/shanghai/5014/overview",
    ),
    ("wta", "381", "2026"): SurfaceReview(
        "Hard",
        ("Dongfeng Voyah Wuhan Open",),
        WTA_CALENDAR,
        "WTA 1000",
    ),
    ("wta", "1020", "2026"): SurfaceReview(
        "Clay",
        ("Vanda Pharmaceuticals Mallorca Women's Championships",),
        WTA_CALENDAR,
        "WTA 125",
    ),
    ("wta", "1025", "2026"): SurfaceReview(
        "Hard",
        ("RoveretOpen Città della Pace",),
        WTA_CALENDAR,
        "WTA 125",
    ),
    ("wta", "1079", "2026"): SurfaceReview(
        "Clay",
        ("Lisboa Belem Open",),
        WTA_CALENDAR,
        "WTA 125",
    ),
    ("wta", "345", "2026"): SurfaceReview(
        "Hard",
        ("Kinoshita Group Japan Open",),
        WTA_CALENDAR,
        "WTA 250",
    ),
    ("wta", "963", "2026"): SurfaceReview(
        "Hard",
        ("Ningbo Open", "BNB Ningbo Open"),
        WTA_CALENDAR,
        "WTA 500",
    ),
    ("wta", "1037", "2026"): SurfaceReview(
        "Clay",
        ("Río Ladies Open by MundoTênis Tours",),
        WTA_CALENDAR,
        "WTA 125",
    ),
}


def verified_surface(
    tour: str,
    event_id: str,
    event_name: str,
    commence_time: datetime,
    venue: str = "",
) -> SurfaceReview | None:
    """Unknown names/seasons never inherit a surface from a coincident provider ID."""
    return _cached_review(
        tour, event_id, _normalize(event_name), commence_time.date(), _normalize(venue)
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


@lru_cache(maxsize=512)
def _cached_review(
    tour: str, event_id: str, name: str, match_date: date, venue: str
) -> SurfaceReview | None:
    """Cache successes and misses; checked-in reviews expire at their event boundary.

    No remote requests occur during forecasting. New evidence requires a source
    revision and process restart, which also invalidates this bounded cache.
    """
    identifier, separator, season = event_id.partition("-")
    if not separator or season != str(match_date.year):
        return None
    review = REVIEWS.get((tour, identifier, season))
    if review is None:
        return None
    if name not in {_normalize(alias) for alias in review.names}:
        return None
    if review.venue and venue != _normalize(review.venue):
        return None
    if review.start_date and match_date < review.start_date:
        return None
    if review.end_date and match_date > review.end_date:
        return None
    return review
