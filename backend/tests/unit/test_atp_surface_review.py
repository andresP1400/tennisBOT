"""Official event facts cannot leak across venues, dates or provider identities."""

from datetime import datetime, timezone

import pytest

from features.personal_schedule import Scoreboard, parse_fixtures
from features.personal_surfaces import verified_surface


@pytest.mark.parametrize(
    "identifier,name,venue,official_id",
    [
        ("708-2026", "Almaty Open", "Almaty, Kazakhstan", "9410"),
        ("440-2026", "BNP Paribas Fortis European Open", "Brussels, Belgium", "7485"),
    ],
)
def test_current_atp_draws_match_official_factual_surface_cache(
    identifier, name, venue, official_id
):
    now = datetime(2026, 10, 19, tzinfo=timezone.utc)
    review = verified_surface("atp", identifier, name, now, venue)
    assert review is not None
    assert review.surface == "Hard"
    assert review.level == "ATP 250"
    assert review.source.endswith(f"/2026/{official_id}/mds.pdf")
    assert verified_surface("atp", identifier, name, now, venue) is review


@pytest.mark.parametrize(
    "identifier,name,venue,year,month,day",
    [
        ("708-2026", "Almaty Open", "", 2026, 10, 19),
        ("708-2026", "Almaty Open", "Astana, Kazakhstan", 2026, 10, 19),
        (
            "440-2026",
            "BNP Paribas Fortis European Open",
            "Antwerp, Belgium",
            2026,
            10,
            19,
        ),
        ("708-2026", "Astana Open", "Almaty, Kazakhstan", 2026, 10, 19),
        ("708-2026", "Almaty Open", "Almaty, Kazakhstan", 2026, 10, 16),
        ("708-2026", "Almaty Open", "Almaty, Kazakhstan", 2026, 10, 26),
        ("708-2027", "Almaty Open", "Almaty, Kazakhstan", 2027, 10, 19),
        ("110-2026", "Grand Prix Auvergne-Rhône-Alpes", "Lyon, France", 2026, 10, 19),
        ("452-2026", "Grand Prix Auvergne-Rhône-Alpes", "Lyon, France", 2026, 10, 19),
    ],
)
def test_unverified_or_expired_identity_remains_unavailable(
    identifier, name, venue, year, month, day
):
    for _ in range(2):
        assert (
            verified_surface(
                "atp",
                identifier,
                name,
                datetime(year, month, day, tzinfo=timezone.utc),
                venue,
            )
            is None
        )


@pytest.mark.parametrize("venue,expected", [("Almaty, Kazakhstan", "Hard"), ("", None)])
def test_scoreboard_passes_tournament_venue_to_surface_verification(venue, expected):
    board = Scoreboard.model_validate(
        {
            "events": [
                {
                    "id": "708-2026",
                    "name": "Almaty Open",
                    "venue": {"displayName": venue},
                    "groupings": [
                        {
                            "grouping": {"slug": "mens-singles"},
                            "competitions": [
                                {
                                    "id": "unit",
                                    "date": "2026-10-19T06:30:00Z",
                                    "status": {
                                        "type": {
                                            "state": "pre",
                                            "name": "STATUS_SCHEDULED",
                                        }
                                    },
                                    "competitors": [
                                        {"athlete": {"displayName": name}}
                                        for name in ["One", "Two"]
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    fixtures = parse_fixtures(board, "atp", datetime(2026, 10, 18, tzinfo=timezone.utc))
    assert len(fixtures) == 1
    assert fixtures[0].surface == expected
