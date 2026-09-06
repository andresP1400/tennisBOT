"""Helper functions for the feature-building pipeline.

All functions here are called by build_features() in features/builder.py.
Split out to keep every file under the 300-line AGENT.md budget; the
symmetric-row feature math lives in features/builder_symmetric.py.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd

from logging_config import get_logger

logger = get_logger(__name__)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def compute_news_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute player news features (injury, form, coach change) for batch training.

    For historical training data, this uses heuristic defaults (no live API calls).
    Live news features are only available via the API /api/player-news endpoint.
    """
    news_cols = [
        "injury_flag_diff",
        "injury_severity_diff",
        "form_sentiment_diff",
        "coach_change_diff",
    ]
    for col in news_cols:
        if col not in df.columns:
            df[col] = 0.0
    return df


def build_player_metadata(df_original: pd.DataFrame) -> dict[str, Any]:
    """Last known bio/ranking data per player (id -> dict) for live inference."""
    date_col = (
        "match_date_est" if "match_date_est" in df_original.columns else "tourney_date"
    )
    sides = []
    for prefix in ["winner", "loser"]:
        cols = {
            f"{prefix}_id": "player_id",
            f"{prefix}_name": "name",
            f"{prefix}_hand": "hand",
            f"{prefix}_ht": "ht",
            f"{prefix}_ioc": "ioc",
            f"{prefix}_age": "age",
            f"{prefix}_rank": "rank",
            f"{prefix}_rank_points": "rank_points",
        }
        available = {k: v for k, v in cols.items() if k in df_original.columns}
        side = df_original[list(available.keys()) + [date_col]].rename(
            columns=available
        )
        side = side.rename(columns={date_col: "last_match_date"})
        sides.append(side)

    long_df = pd.concat(sides, ignore_index=True)
    long_df = long_df.sort_values("last_match_date")
    latest = long_df.groupby("player_id").last()
    players = latest.to_dict(orient="index")
    name_to_id = {
        str(row["name"]).lower(): pid
        for pid, row in players.items()
        if isinstance(row.get("name"), str)
    }
    return {"players": players, "name_to_id": name_to_id}


def save_inference_state(
    df_original: pd.DataFrame,
    tour: str,
    elo_state: Any,
    rolling_state: Any,
    fatigue_state: Any,
    h2h_state: Any,
) -> None:
    """Serialize post-build tracker states for live inference."""
    import joblib
    from datetime import datetime

    logger.info("\n  Saving inference state (tracker snapshots) ...")
    meta = build_player_metadata(df_original)
    state = {
        "tour": tour,
        "built_at": datetime.now().isoformat(),
        "data_through": str(df_original["tourney_date"].max()),
        "elo": elo_state,
        "rolling": rolling_state,
        "fatigue": fatigue_state,
        "h2h": h2h_state,
        "players": meta["players"],
        "name_to_id": meta["name_to_id"],
    }
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    state_path = os.path.join(config.PROCESSED_DIR, f"{tour}_inference_state.pkl")
    joblib.dump(state, state_path, compress=3)
    size_mb = os.path.getsize(state_path) / 1e6
    logger.info(
        f"  Inference state saved to: {state_path} ({size_mb:.1f} MB, "
        f"{len(meta['players']):,} players)"
    )
