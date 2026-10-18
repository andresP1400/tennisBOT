"""Guard result identities, completion, chronology and immutable source bytes."""

from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
import pytest

from data.result_adapters import (
    convert_official,
    official_player_names,
    select_official_singles,
)
from data.result_extension import reconcile_results
from data.result_identities import identity_aliases
from data.result_sources import checked_bytes
from data.result_statistics import retained_statistics, tml_results
from pipeline.personal_data import build_dataset


def history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "winner_id": 1,
                "winner_name": "John Smith",
                "loser_id": 2,
                "loser_name": "Alex Jones",
                "date": pd.Timestamp("2026-01-01"),
                "surface": "Hard",
                "best_of": 3,
                "score": "6-4 6-4",
                "tourney_id": "base",
                "match_num": 1,
            }
        ]
    )


def candidate(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "date": pd.Timestamp("2026-03-01"),
        "first": "Smith J.",
        "second": "Jones A.",
        "winner_first": True,
        "event": "Reviewed event",
        "surface": "Hard",
        "score": "6-4 6-4",
        "best_of": 3,
        "rank1": -1,
        "rank2": 10,
        "points1": -1,
        "points2": 500,
        "source_id": "one",
    }
    return row | changes


def test_shared_initials_are_not_resolved_to_a_different_player() -> None:
    frame = pd.concat(
        [history(), history().assign(winner_id=3, winner_name="Jane Smith")]
    )
    aliases = identity_aliases(frame)
    assert "smith j" not in aliases
    assert aliases["john smith"][0] == 1


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"date": pd.Timestamp("2099-01-01")}, "invalid_or_future_date"),
        ({"date": pd.Timestamp("2025-12-01")}, "existing_historical_prefix"),
        ({"first": "Unresolved J."}, "unresolved_or_ambiguous_identity"),
        ({"score": "6-2 RET"}, "incomplete_result"),
        ({"surface": "Unknown"}, "missing_surface_or_score"),
    ],
)
def test_unusable_results_are_excluded(change: dict[str, object], reason: str) -> None:
    result, audit = reconcile_results(history(), pd.DataFrame([candidate(**change)]))
    assert result.empty
    assert audit[reason] == 1


def test_missing_rankings_and_point_statistics_are_not_fabricated() -> None:
    result, _ = reconcile_results(history(), pd.DataFrame([candidate()]))
    assert len(result) == 1
    assert pd.isna(result.iloc[0].winner_rank)
    assert pd.isna(result.iloc[0].winner_rank_points)
    assert result.iloc[0].loser_rank == 10
    assert "w_svpt" not in result


def test_duplicate_perspectives_count_once_and_contradictions_are_withheld() -> None:
    result, audit = reconcile_results(
        history(), pd.DataFrame([candidate(), candidate()])
    )
    assert len(result) == 1 and audit["duplicate_perspective"] == 1
    result, audit = reconcile_results(
        history(), pd.DataFrame([candidate(), candidate(winner_first=False)])
    )
    assert result.empty and audit["conflicting_outcomes"] == 1


def test_potential_legacy_overlap_is_not_double_counted() -> None:
    result, audit = reconcile_results(
        history(), pd.DataFrame([candidate(date=pd.Timestamp("2026-01-05"))])
    )
    assert result.empty and audit["possible_legacy_overlap"] == 1


def test_appending_results_cannot_change_earlier_features() -> None:
    base = history()
    extra, _ = reconcile_results(base, pd.DataFrame([candidate()]))
    original, _ = build_dataset(base, feature_schema=2)
    extended, _ = build_dataset(
        pd.concat([base, extra], ignore_index=True), feature_schema=2
    )
    np.testing.assert_array_equal(original.iloc[0].features, extended.iloc[0].features)
    assert extended.iloc[1].available_at == pd.Timestamp("2026-03-22")
    assert extended.iloc[1].player1_matches == 1


def test_official_wta_ids_override_misaligned_draw_names() -> None:
    raw = pd.DataFrame(
        {
            "player_1": [10, 20],
            "player_2": [20, 10],
            "winner": [1, 2],
            "team_name_1": ["WRONG DRAW ORDER"] * 2,
            "team_name_2": ["DO NOT USE"] * 2,
            "startDate": ["2026-03-01"] * 2,
            "title": ["Event"] * 2,
            "surface": ["Hard"] * 2,
            "scores": ["6-4 6-4"] * 2,
            "rank_1": [5, 10],
            "rank_2": [10, 5],
            "pseudo_tournament_id": [100] * 2,
            "round_name": ["F"] * 2,
        }
    )
    converted = convert_official(raw, {10: "John Smith", 20: "Alex Jones"})
    result, audit = reconcile_results(history(), converted)
    assert len(result) == 1 and result.iloc[0].winner_id == 1
    assert audit["conflicting_outcomes"] == 0
    assert pd.isna(result.iloc[0].winner_rank_points)


def test_qualifying_doubles_retirements_and_byes_cannot_supply_labels() -> None:
    raw = pd.DataFrame(
        {
            "pseudo_tournament_id": [1] * 5,
            "qpm_flag": ["M", "Q", "M", "M", "M"],
            "reason_code": ["W", "W", "R", "B", "W"],
            "player_3": [np.nan] * 4 + [3],
            "player_4": [np.nan] * 5,
            "winner": [1] * 5,
        }
    )
    assert (
        len(select_official_singles(raw, pd.DataFrame({"pseudo_tournament_id": [1]})))
        == 1
    )


def test_checksum_failure_preserves_existing_bytes(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.csv"
    path.write_bytes(b"existing private data")
    with pytest.raises(ValueError, match="checksum"):
        checked_bytes(path, hashlib.sha256(b"expected bytes").hexdigest())
    assert path.read_bytes() == b"existing private data"


def test_country_duplicates_are_safe_but_conflicting_player_names_stay_unresolved() -> (
    None
):
    players = pd.DataFrame(
        {
            "playerId": [1, 1, 2, 2],
            "fullName": ["John Smith", "John Smith", "Jane Doe", "Janet Roe"],
        }
    )
    assert official_player_names(players) == {1: "John Smith"}


def test_detailed_source_counts_are_preserved_without_zero_imputation() -> None:
    row = pd.Series(
        {
            "detailed_statistics": np.bool_(True),
            "w_1stWon": 30,
            "w_2ndWon": np.nan,
            "w_svpt": 60,
        }
    )
    counts = retained_statistics(row)
    assert counts["w_1stWon"] == 30 and counts["w_svpt"] == 60
    assert pd.isna(counts["w_2ndWon"])


def test_unreviewed_csv_cannot_enter_a_detailed_source(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "tourney_date": [20260301],
            "winner_name": ["John Smith"],
            "loser_name": ["Alex Jones"],
            "tourney_name": ["Event"],
            "tourney_id": ["one"],
            "match_num": [1],
            "tourney_level": ["A"],
            "winner_rank": [1],
            "loser_rank": [2],
            "winner_rank_points": [10],
            "loser_rank_points": [5],
        }
    )
    frame.to_csv(tmp_path / "reviewed.csv", index=False)
    (tmp_path / "unreviewed.csv").write_text("malformed and untrusted")
    assert len(tml_results(tmp_path, ("reviewed.csv",))) == 1


def test_birth_date_in_height_field_cannot_corrupt_player_state() -> None:
    row = pd.Series(
        {
            "detailed_statistics": True,
            "winner_ht": 20080331,
            "loser_ht": 175,
            "winner_age": 0,
            "loser_age": 25,
            "w_1stWon": 20,
        }
    )
    values = retained_statistics(row)
    assert pd.isna(values["winner_ht"]) and pd.isna(values["winner_age"])
    assert values["loser_ht"] == 175 and values["loser_age"] == 25
    assert values["w_1stWon"] == 20


def test_source_event_level_and_round_survive_identity_remapping() -> None:
    result, _ = reconcile_results(
        history(),
        pd.DataFrame(
            [
                candidate(
                    tourney_level="250",
                    round="SF",
                    tourney_id="provider-event",
                    winner_id="foreign-id",
                ),
            ]
        ),
    )
    row = result.iloc[0]
    assert row.tourney_level == "250" and row["round"] == "SF"
    assert (
        row.source_event_id == "provider-event" and row.source_winner_id == "foreign-id"
    )
    assert row.winner_id == 1
