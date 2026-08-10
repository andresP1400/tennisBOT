"""
Live inference from serialized tracker state.

The feature builder saves the FINAL state of every tracker (ELO, rolling
stats, fatigue, H2H) plus per-player metadata. This module rebuilds the
exact same features the model was trained on, but CURRENT:
  - up-to-date ELO (including the player's last match result)
  - rolling form as of today
  - real days_rest / weekly load relative to today's date
  - true head-to-head between the two players

This replaces the old approach of reading stale pre-match rows from the
parquet, which used each player's last match snapshot (wrong surface,
wrong date, no H2H).
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Bases whose snapshot keys differ from the diff-column prefix
_BASE_KEY_MAP = {"ranking": "rank", "ranking_points": "rank_points"}


def load_inference_state(tour: str = "atp"):
    """Load the tracker state saved by the feature builder. None if missing."""
    state_path = os.path.join(config.PROCESSED_DIR, f"{tour}_inference_state.pkl")
    if not os.path.exists(state_path):
        return None
    return joblib.load(state_path)


def resolve_player_id(state: dict, player_name: str):
    """Map a player name to their Sackmann id (case-insensitive)."""
    return state["name_to_id"].get(player_name.strip().lower())


def player_snapshot(state: dict, player_id, surface: str, now: pd.Timestamp) -> dict:
    """Current feature values for one player, as of `now`."""
    snap = {}

    # --- ELO (with inactivity decay relative to today) ---
    elo = state["elo"]
    elo.apply_inactivity_decay(player_id, now)
    snap["elo"] = elo.get_rating(player_id)
    snap["elo_surface"] = elo.get_rating(player_id, surface)
    snap["elo_blend"] = elo.get_blended_rating(player_id, surface)
    snap["elo_match_count"] = elo.get_match_count(player_id)

    # --- Rolling form ---
    tracker = state["rolling"].get(player_id)
    if tracker is not None:
        snap.update(tracker.get_rolling_stats(surface))

    # --- Fatigue relative to TODAY ---
    fat = state["fatigue"].get(player_id)
    if fat is not None:
        snap.update(fat.get_fatigue_stats(now))

    # --- Bio / ranking metadata (last known) ---
    meta = state["players"].get(player_id, {})
    snap["rank"] = meta.get("rank", np.nan)
    snap["rank_points"] = meta.get("rank_points", np.nan)
    snap["hand"] = meta.get("hand", "U")
    snap["ht"] = meta.get("ht", np.nan)
    snap["ioc"] = meta.get("ioc", "")
    last_date = meta.get("last_match_date")
    age = meta.get("age", np.nan)
    if last_date is not None and not pd.isna(last_date) and not pd.isna(age):
        snap["age"] = float(age) + (now - pd.Timestamp(last_date)).days / 365.25
        snap["days_since_last_match"] = (now - pd.Timestamp(last_date)).days
    else:
        snap["age"] = age
        snap["days_since_last_match"] = None

    return snap


def _diff(snap_a: dict, snap_b: dict, base: str):
    key = _BASE_KEY_MAP.get(base, base)
    va, vb = snap_a.get(key, np.nan), snap_b.get(key, np.nan)
    try:
        va, vb = float(va), float(vb)
    except (TypeError, ValueError):
        return np.nan
    if np.isnan(va) or np.isnan(vb):
        return np.nan
    return va - vb


def build_match_features(
    state: dict,
    feature_cols: list,
    snap_a: dict,
    snap_b: dict,
    id_a,
    id_b,
    surface: str,
    best_of: int = 3,
    tourney_level_encoded: int = 2,
    round_encoded: int = 3,
    odds_a: float = None,
    odds_b: float = None,
    now: pd.Timestamp = None,
) -> pd.DataFrame:
    """Build the model input row for player A vs player B."""
    now = now or pd.Timestamp.now()
    h2h = state["h2h"].get_h2h(id_a, id_b, surface) if (id_a is not None and id_b is not None) \
        else {"h2h_win_pct": np.nan, "h2h_win_pct_surface": np.nan, "h2h_total_matches": 0}

    row = pd.DataFrame(np.nan, index=[0], columns=feature_cols)

    for col in feature_cols:
        if col.startswith("surface_"):
            row[col] = 1.0 if col == f"surface_{surface}" else 0.0
        elif col == "tourney_level_encoded":
            row[col] = tourney_level_encoded
        elif col == "round_encoded":
            row[col] = round_encoded
        elif col == "best_of":
            row[col] = best_of
        elif col == "month":
            row[col] = now.month
        elif col == "indoor_outdoor":
            row[col] = 0
        elif col == "altitude":
            row[col] = 0.0
        elif col == "h2h_win_pct":
            row[col] = h2h["h2h_win_pct"]
        elif col == "h2h_win_pct_surface":
            row[col] = h2h["h2h_win_pct_surface"]
        elif col == "hand_matchup":
            hand_a = str(snap_a.get("hand", "U"))
            hand_b = str(snap_b.get("hand", "U"))
            row[col] = int(hand_a != hand_b) if "U" not in (hand_a, hand_b) else 0
        elif col == "home_country_flag":
            row[col] = 0  # tournament unknown at inference
        elif col == "qualifier_flag_diff":
            row[col] = 0
        elif col == "cold_start_flag":
            ca = snap_a.get("match_count", 0) or 0
            cb = snap_b.get("match_count", 0) or 0
            row[col] = int(ca < config.COLD_START_THRESHOLD or cb < config.COLD_START_THRESHOLD)
        elif col == "log_rank_diff":
            ra, rb = snap_a.get("rank", np.nan), snap_b.get("rank", np.nan)
            try:
                ra, rb = float(ra), float(rb)
                if not np.isnan(ra) and not np.isnan(rb):
                    row[col] = np.log(max(ra, 1.0)) - np.log(max(rb, 1.0))
            except (TypeError, ValueError):
                pass
        elif col == "elo_diff_x_bo5":
            row[col] = _diff(snap_a, snap_b, "elo") * (1 if best_of == 5 else 0)
        elif col == "opening_odds_diff":
            if odds_a is not None and odds_b is not None and odds_a > 1.0 and odds_b > 1.0:
                row[col] = float(odds_a) - float(odds_b)
        elif col.endswith("_diff"):
            row[col] = _diff(snap_a, snap_b, col[: -len("_diff")])
        # anything else stays NaN -> training-median via the imputer

    return row


def assess_reliability(snap_a: dict, snap_b: dict, h2h_total: int, found_a: bool, found_b: bool) -> dict:
    """Qualitative confidence flag for the prediction.

    A probability built on two unknown players is worth much less than one
    on two established tour regulars: the caller should know which is which.
    """
    reasons = []
    score = 2  # alta

    if not found_a or not found_b:
        return {"level": "bassa", "reasons": ["giocatore non trovato nello storico (cold start totale)"]}

    for label, snap in [("p1", snap_a), ("p2", snap_b)]:
        count = snap.get("match_count", 0) or 0
        if count < config.COLD_START_THRESHOLD:
            score -= 2
            reasons.append(f"{label}: solo {int(count)} match nello storico (cold start)")
        elif count < 30:
            score -= 1
            reasons.append(f"{label}: storico limitato ({int(count)} match)")

        staleness = snap.get("days_since_last_match")
        if staleness is not None and staleness > 365:
            score -= 2
            reasons.append(f"{label}: inattivo da {int(staleness)} giorni")
        elif staleness is not None and staleness > 180:
            score -= 1
            reasons.append(f"{label}: ultimo match {int(staleness)} giorni fa")

    if h2h_total == 0:
        reasons.append("nessun precedente diretto tra i due giocatori")

    level = "alta" if score >= 2 else ("media" if score >= 0 else "bassa")
    return {"level": level, "reasons": reasons}
