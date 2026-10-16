"""Cross-provider identities must be reviewed; coincident numeric IDs are unsafe."""

from datetime import datetime, timezone

import pytest

from api.personal_engine import forecast_warning, analyze_fixture
from features.personal_schedule import Fixture
from features.personal_surfaces import verified_surface


@pytest.mark.parametrize(
    "identifier,name,surface",
    [
        ("1020-2026", "Vanda Pharmaceuticals Mallorca Women's Championships", "Clay"),
        ("1025-2026", "RoveretOpen Città della Pace", "Hard"),
        ("1079-2026", "Lisboa Belem Open", "Clay"),
        ("381-2026", "Dongfeng Voyah Wuhan Open", "Hard"),
        ("345-2026", "Kinoshita Group Japan Open", "Hard"),
        ("963-2026", "Ningbo Open", "Hard"),
        ("1037-2026", "Río Ladies Open by MundoTênis Tours", "Clay"),
    ],
)
def test_reviewed_official_calendar_and_provider_id_agree(identifier, name, surface):
    review = verified_surface(
        "wta", identifier, name, datetime(2026, 10, 16, tzinfo=timezone.utc)
    )
    assert review is not None
    assert review.surface == surface
    assert review.source.startswith("https://api.wtatennis.com/")


@pytest.mark.parametrize(
    "tour,identifier,name,year",
    [
        ("wta", "1020-2026", "China Open", 2026),
        (
            "wta",
            "1020-2027",
            "Vanda Pharmaceuticals Mallorca Women's Championships",
            2027,
        ),
        (
            "wta",
            "1020-2026",
            "Vanda Pharmaceuticals Mallorca Women's Championships",
            2027,
        ),
        (
            "atp",
            "1020-2026",
            "Vanda Pharmaceuticals Mallorca Women's Championships",
            2026,
        ),
        ("wta", "1020", "Vanda Pharmaceuticals Mallorca Women's Championships", 2026),
    ],
)
def test_unknown_season_tour_or_coincident_id_never_implies_a_surface(
    tour, identifier, name, year
):
    assert (
        verified_surface(
            tour, identifier, name, datetime(year, 10, 16, tzinfo=timezone.utc)
        )
        is None
    )


def test_lower_tier_forecasts_warn_about_unvalidated_accuracy_and_block_ev():
    fixture = Fixture(
        id="unit",
        tour="wta",
        player1="One",
        player2="Two",
        tournament="Unit WTA 125",
        tournament_level="WTA 125",
        surface="Clay",
        commence_time=datetime(2026, 10, 17, tzinfo=timezone.utc),
        source="unit",
        fetched_at=datetime.now(timezone.utc),
        odds1=2,
        odds2=2,
        odds_observed_at=datetime.now(timezone.utc),
    )
    assert "does not establish performance" in forecast_warning(fixture, 1)
    analysis = analyze_fixture(0.7, fixture, 1)
    assert not analysis["player1"]["eligible"]
    assert analysis["player1"]["stake_fraction"] == 0
    assert "Calibration provenance is unavailable" in analysis["player1"]["reasons"]
    fixture.tournament_level = "WTA 1000"
    assert forecast_warning(fixture, 1) is None
