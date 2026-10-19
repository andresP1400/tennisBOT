"""Convert completed provider results without inventing identities or statistics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.personal_state import normalize_name


def abbreviated_results(directory: Path) -> pd.DataFrame:
    """The ATP export has actual match dates, rankings and scores, but no point counts."""
    frame = pd.read_csv(directory / "atp_tennis.csv", low_memory=False)
    frame["date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["first"] = frame["Player_1"]
    frame["second"] = frame["Player_2"]
    frame["winner_first"] = frame["Winner"] == frame["Player_1"]
    valid = frame["Winner"].eq(frame["Player_1"]) | frame["Winner"].eq(
        frame["Player_2"]
    )
    frame = frame.loc[valid].copy()
    frame["event"] = frame["Tournament"]
    frame["surface"] = frame["Surface"]
    frame["score"] = frame["Score"]
    frame["best_of"] = frame["Best of"]
    for side in (1, 2):
        frame[f"rank{side}"] = pd.to_numeric(frame[f"Rank_{side}"], errors="coerce")
        frame[f"points{side}"] = pd.to_numeric(frame[f"Pts_{side}"], errors="coerce")
    frame["source_id"] = (
        frame["Tournament"].astype(str)
        + ":"
        + frame["Date"].astype(str)
        + ":"
        + frame["Round"].astype(str)
    )
    return frame


def official_wta_results(directory: Path) -> pd.DataFrame:
    """Use only finished main-tour singles events, never qualifying or WTA 125."""
    tournaments = pd.read_csv(directory / "tournaments.csv")
    start = pd.to_datetime(tournaments["startDate"], errors="coerce")
    end = pd.to_datetime(tournaments["endDate"], errors="coerce")
    levels = ["WTA 250", "WTA 500", "WTA 1000", "Grand Slam", "Finals"]
    valid = (
        tournaments["year"].eq(2026)
        & tournaments["level"].isin(levels)
        & (end < pd.Timestamp.today().normalize())
        & (end >= start)
        & ((end - start).dt.days <= 21)
    )
    tournaments = tournaments.loc[valid]
    chunks = []
    for frame in pd.read_csv(
        directory / "matches.csv", chunksize=100000, low_memory=False
    ):
        selected = select_official_singles(frame, tournaments)
        if not selected.empty:
            chunks.append(selected)
    if not chunks:
        raise ValueError("Reviewed WTA snapshot has no completed main-tour singles")
    players = pd.read_csv(directory / "players.csv")
    names = official_player_names(players)
    return convert_official(pd.concat(chunks, ignore_index=True), names)


def official_player_names(players: pd.DataFrame) -> dict[int, str]:
    """Country changes may repeat an identity; conflicting name variants stay unresolved."""
    names = {}
    for identifier, group in players.groupby("playerId"):
        values = group["fullName"].dropna().astype(str)
        if values.map(normalize_name).nunique() == 1:
            names[int(identifier)] = str(values.iloc[0])
    return names


def select_official_singles(
    frame: pd.DataFrame, tournaments: pd.DataFrame
) -> pd.DataFrame:
    """Retirements, byes, defaults and doubles cannot enter the training labels."""
    valid = (
        frame["pseudo_tournament_id"].isin(tournaments["pseudo_tournament_id"])
        & frame["qpm_flag"].eq("M")
        & frame["reason_code"].eq("W")
        & frame["player_3"].isna()
        & frame["player_4"].isna()
        & frame["winner"].isin([1, 2])
    )
    return frame.loc[valid].merge(
        tournaments, on="pseudo_tournament_id", validate="many_to_one"
    )


def convert_official(frame: pd.DataFrame, names: dict[int, str]) -> pd.DataFrame:
    """Perspective IDs, not draw-order team names, align outcomes and rankings."""
    result = pd.DataFrame(index=frame.index)
    result["date"] = pd.to_datetime(frame["startDate"], errors="coerce")
    result["first"] = pd.to_numeric(frame["player_1"], errors="coerce").map(names)
    result["second"] = pd.to_numeric(frame["player_2"], errors="coerce").map(names)
    result["winner_first"] = frame["winner"].eq(1)
    result["event"], result["surface"] = frame["title"], frame["surface"]
    result["score"], result["best_of"] = frame["scores"], 3
    result["rank1"], result["rank2"] = frame["rank_1"], frame["rank_2"]
    result["points1"], result["points2"] = np.nan, np.nan
    result["source_id"] = (
        frame["pseudo_tournament_id"].astype(str)
        + ":"
        + frame["round_name"].astype(str)
    )
    return result
