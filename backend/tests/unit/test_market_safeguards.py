"""Real paired markets, player orientation, and conservative EV admission."""

from dataclasses import replace

import pytest

from features.guarded_ev import guarded_ev
from features.market_math import bookmaker_consensus, valid_price
from features.odds_aggregator import MatchOdds, OddsAggregator


def test_consensus_averages_each_book_after_removing_its_own_margin():
    consensus = bookmaker_consensus(
        {"A": {"player1": 1.5, "player2": 2.4}, "B": {"player1": 2.2, "player2": 1.7}}
    )
    expected = ((1 / 1.5) / (1 / 1.5 + 1 / 2.4) + (1 / 2.2) / (1 / 2.2 + 1 / 1.7)) / 2
    assert consensus.prob1 == pytest.approx(expected)
    assert consensus.prob1 != pytest.approx((1 / 2.2) / (1 / 2.2 + 1 / 2.4))
    assert consensus.prob1 + consensus.prob2 == 1
    assert consensus.books == 2


def test_duplicate_bookmaker_relays_do_not_inflate_consensus():
    prices = {"player1": 1.8, "player2": 2.2}
    consensus = bookmaker_consensus(
        {"direct:Pinnacle": prices, "relay:pinnacle": prices}
    )
    assert consensus.books == 1


@pytest.mark.parametrize("price", [float("nan"), float("inf"), -1, 0, 1])
def test_invalid_market_quotes_are_never_usable(price):
    assert not valid_price(price)
    with pytest.raises(ValueError):
        bookmaker_consensus({"A": {"player1": price, "player2": 2.0}})


def test_reversed_provider_and_query_preserve_players_prices_and_probabilities(
    monkeypatch,
):
    aggregator = OddsAggregator()
    first = MatchOdds(
        "provider",
        "Alpha",
        "Zulu",
        "ATP",
        "2026-10-17T12:00:00Z",
        False,
        1.5,
        2.4,
        "A",
        "atp",
    )
    second = replace(
        first, player1="Zulu", player2="Alpha", odds_p1=1.7, odds_p2=2.2, bookmaker="B"
    )
    matches = aggregator._aggregate([first, second], "atp")
    assert len(matches) == 1
    assert matches[0]["best_odds"] == {"player1": 2.2, "player2": 2.4}
    monkeypatch.setattr(aggregator, "get_today_matches", lambda tour: matches)
    reverse = aggregator.get_match_odds("Zulu", "Alpha")
    assert reverse["player1"] == "Zulu"
    assert reverse["best_odds"] == {"player1": 2.4, "player2": 2.2}
    assert reverse["sources"]["provider:A"]["player1"] == 2.4
    assert reverse["implied_prob1"] == matches[0]["implied_prob2"]
    assert aggregator.get_match_odds("Alpha", "Other") == {}


def trusted(**overrides):
    arguments = dict(
        calibrated=True, model_age_days=2, quote_age_seconds=10, independent_books=2
    )
    arguments.update(overrides)
    return guarded_ev(0.7, 2.0, 0.5, **arguments)


def test_eligible_expected_value_limits_stake_to_one_percent():
    result = trusted()
    assert result.eligible
    assert result.expected_value == pytest.approx(0.4)
    assert result.edge == pytest.approx(0.2)
    assert result.stake_fraction == 0.01
    small = guarded_ev(
        0.515,
        2,
        0.5,
        calibrated=True,
        model_age_days=1,
        quote_age_seconds=0,
        independent_books=3,
        min_edge=0.01,
    )
    assert small.stake_fraction == pytest.approx(0.0075)


@pytest.mark.parametrize(
    "override",
    [
        {"calibrated": False},
        {"model_age_days": 31},
        {"model_age_days": -1},
        {"quote_age_seconds": None},
        {"quote_age_seconds": 301},
        {"quote_age_seconds": -1},
        {"quote_age_seconds": float("nan")},
        {"independent_books": 1},
        {"min_edge": 0.3},
    ],
)
def test_missing_provenance_stale_data_or_insufficient_edge_block_staking(override):
    result = trusted(**override)
    assert not result.eligible
    assert result.stake_fraction == 0
    assert result.reasons


def test_missing_odds_commission_and_invalid_model_probabilities():
    assert guarded_ev(0.7, None, None).expected_value is None
    assert not trusted(commission=0.9).eligible
    assert not guarded_ev(0.7, 2, float("nan")).eligible
    for probability in [float("nan"), float("inf"), -0.1, 1.1]:
        with pytest.raises(ValueError):
            guarded_ev(probability, 2, 0.5)


def test_optional_odds_adapter_keeps_paired_books_before_price_shopping():
    from features.odds_theoddsapi_data import parse_event

    event = {
        "home_team": "Alpha",
        "away_team": "Zulu",
        "commence_time": "2026-10-17T12:00:00Z",
        "bookmakers": [
            {
                "key": book,
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Alpha", "price": first},
                            {"name": "Zulu", "price": second},
                        ],
                    }
                ],
            }
            for book, first, second in [("a", 1.5, 2.4), ("b", 2.2, 1.7)]
        ],
    }
    quotes = parse_event(event, "tennis_atp_shanghai")
    assert [(quote.bookmaker, quote.odds_p1, quote.odds_p2) for quote in quotes] == [
        ("a", 1.5, 2.4),
        ("b", 2.2, 1.7),
    ]
    event["bookmakers"][0]["markets"][0]["outcomes"].pop()
    assert len(parse_event(event, "tennis_atp_shanghai")) == 1


def test_same_players_on_different_days_never_share_bookmaker_consensus():
    aggregator = OddsAggregator()
    first = MatchOdds(
        "provider",
        "Alpha",
        "Zulu",
        "ATP",
        "2026-10-17T12:00:00Z",
        False,
        1.5,
        2.4,
        "a",
        "atp",
    )
    later = replace(
        first, commence_time="2026-10-18T12:00:00Z", odds_p1=2.2, odds_p2=1.7
    )
    matches = aggregator._aggregate([first, later], "atp")
    assert len(matches) == 2
    assert matches[0]["implied_prob1"] != matches[1]["implied_prob1"]


def test_live_market_path_ignores_incomplete_and_nonfinite_quotes():
    from features.live_odds_match_odds import MatchOddsMixin

    class Scraper(MatchOddsMixin):
        enable_scraping = False

        def _get_api_key(self):
            return "unit-test-placeholder"

        def _scrape_theoddsapi(self, player1, player2):
            return {
                "a": {"player1": 1.5, "player2": 2.4},
                "b": {"player1": 2.2, "player2": 1.7},
                "bad": {"player1": float("inf"), "player2": 4},
                "missing": {"player1": 3},
            }

    result = Scraper().get_match_odds("Unit One", "Unit Two", force_refresh=True)
    assert result["best_odds"] == {"player1": 2.2, "player2": 2.4}
    assert set(result["sources"]) == {"a", "b"}
    assert result["implied_prob1"] == bookmaker_consensus(result["sources"]).prob1
