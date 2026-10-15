"""Reviewed season-specific surfaces with explicit cross-provider identities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SurfaceReview:
    surface: str
    names: tuple[str, ...]
    source: str
    level: str | None = None


WTA_CALENDAR = "https://api.wtatennis.com/tennis/tournaments/?page=0&pageSize=100&from=2026-10-01&to=2026-10-31"

# ESPN identifiers differ from WTA's; names and season must also agree.
REVIEWS = {
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
}


def verified_surface(
    tour: str, event_id: str, event_name: str, commence_time: datetime
) -> SurfaceReview | None:
    """Unknown names/seasons never inherit a surface from a coincident provider ID."""
    identifier, separator, season = event_id.partition("-")
    if not separator or season != str(commence_time.year):
        return None
    review = REVIEWS.get((tour, identifier, season))
    if review is None:
        return None
    normalized = " ".join(event_name.casefold().split())
    return (
        review
        if normalized in {" ".join(name.casefold().split()) for name in review.names}
        else None
    )
