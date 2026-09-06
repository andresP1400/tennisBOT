"""
ELO rating system for tennis players.

Computes:
  - elo_global     : overall ELO across all surfaces
  - elo_surface    : surface-specific ELO (Hard, Clay, Grass, Carpet)
  - elo_blend      : surface ELO shrunk toward global ELO when the player
                     has few matches on the surface

Refinements over plain ELO:
  - K-factor scaled by tournament level (Slam > Masters > 250 > Challenger)
  - Margin-of-victory bonus (straight-set wins move ratings more)
  - Inactivity decay (long layoffs regress ratings toward the mean)

CRITICAL: ratings are computed forward-only.
The ELO at match time uses ONLY data from matches BEFORE the current one.
"""

import os
import sys
import re
from typing import Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_SET_PATTERN = re.compile(r"(\d+)-(\d+)")


def _sets_margin(score: str | None) -> int:
    """Sets won by the winner minus sets won by the loser (>= 1).

    Returns 1 when the score is unparseable so the MOV bonus is neutral.
    """
    if not score or not isinstance(score, str):
        return 1
    w_sets = l_sets = 0
    for token in score.split():
        clean = re.sub(r"\(\d+\)", "", token)
        m = _SET_PATTERN.fullmatch(clean)
        if not m:
            continue
        s1, s2 = int(m.group(1)), int(m.group(2))
        if s1 > s2:
            w_sets += 1
        elif s2 > s1:
            l_sets += 1
    margin = w_sets - l_sets
    return margin if margin >= 1 else 1


class EloRatingSystem:
    """Forward-only ELO with surface variants, level/MOV-scaled K and
    inactivity decay."""

    def __init__(
        self,
        k_factor: float | None = None,
        initial_rating: float | None = None,
    ) -> None:
        self.k = k_factor or config.ELO_K_FACTOR
        self.initial = initial_rating or config.ELO_INITIAL

        # Plain dicts (not defaultdicts) so the state is picklable for
        # inference-time use.
        self.ratings_global: dict[int, float] = {}  # player_id -> float
        self.ratings_surface: dict[tuple[int, str], float] = (
            {}
        )  # (player_id, surface) -> float
        self.match_counts: dict[int, int] = {}  # player_id -> int
        self.match_counts_surface: dict[tuple[int, str], int] = (
            {}
        )  # (player_id, surface) -> int
        self.last_date: dict[int, pd.Timestamp] = {}  # player_id -> pd.Timestamp

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Standard ELO expected score for player A."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def _adaptive_k(self, player_id: int, surface: str | None = None) -> float:
        """K-factor that adapts based on number of matches played.
        Higher K for newer players (faster convergence), lower for established.
        """
        if surface:
            count = self.match_counts_surface.get((player_id, surface), 0)
        else:
            count = self.match_counts.get(player_id, 0)

        if count < 10:
            return self.k * 1.5  # new player: faster learning
        elif count < 30:
            return self.k * 1.2
        else:
            return self.k

    @staticmethod
    def _level_mult(level: str | None) -> float:
        return config.ELO_LEVEL_K_MULT.get(level or "", 1.0)

    @staticmethod
    def _mov_mult(score: str | None) -> float:
        margin = _sets_margin(score)
        return 1.0 + config.ELO_MOV_BONUS_PER_SET * (margin - 1)

    def apply_inactivity_decay(
        self, player_id: int, current_date: pd.Timestamp | None
    ) -> None:
        """Regress ratings toward the initial value after long layoffs.

        Must be called BEFORE reading pre-match ratings. Idempotent within
        the same date (last_date is advanced after the decay is applied).
        """
        if current_date is None or pd.isna(current_date):
            return
        last = self.last_date.get(player_id)
        if last is None or pd.isna(last):
            return
        gap = (current_date - last).days
        if gap <= config.ELO_INACTIVITY_GRACE_DAYS:
            return

        factor = 0.5 ** (
            (gap - config.ELO_INACTIVITY_GRACE_DAYS)
            / config.ELO_INACTIVITY_HALF_LIFE_DAYS
        )
        if player_id in self.ratings_global:
            r = self.ratings_global[player_id]
            self.ratings_global[player_id] = self.initial + (r - self.initial) * factor
        for surf in config.SURFACES:
            key = (player_id, surf)
            if key in self.ratings_surface:
                r = self.ratings_surface[key]
                self.ratings_surface[key] = self.initial + (r - self.initial) * factor
        # Advance the marker so the decay is not applied twice
        self.last_date[player_id] = current_date

    def update(
        self,
        winner_id: int,
        loser_id: int,
        surface: str | None = None,
        level: str | None = None,
        score: str | None = None,
        date: pd.Timestamp | None = None,
    ) -> dict[str, Any]:
        """Update ELO ratings after a match result.

        MUST be called AFTER the feature row has been created using the
        pre-match ratings.
        """
        k_scale = self._level_mult(level) * self._mov_mult(score)

        # --- Global ELO ---
        r_w = self.ratings_global.get(winner_id, float(self.initial))
        r_l = self.ratings_global.get(loser_id, float(self.initial))

        exp_w = self.expected_score(r_w, r_l)
        exp_l = 1.0 - exp_w

        k_w = self._adaptive_k(winner_id) * k_scale
        k_l = self._adaptive_k(loser_id) * k_scale

        new_r_w = r_w + k_w * (1.0 - exp_w)
        new_r_l = r_l + k_l * (0.0 - exp_l)

        self.ratings_global[winner_id] = new_r_w
        self.ratings_global[loser_id] = new_r_l
        self.match_counts[winner_id] = self.match_counts.get(winner_id, 0) + 1
        self.match_counts[loser_id] = self.match_counts.get(loser_id, 0) + 1

        result = {
            "winner_elo_before": r_w,
            "loser_elo_before": r_l,
            "winner_elo_after": new_r_w,
            "loser_elo_after": new_r_l,
        }

        # --- Surface ELO ---
        if surface and surface in config.SURFACES:
            sr_w = self.ratings_surface.get((winner_id, surface), float(self.initial))
            sr_l = self.ratings_surface.get((loser_id, surface), float(self.initial))

            s_exp_w = self.expected_score(sr_w, sr_l)

            sk_w = self._adaptive_k(winner_id, surface) * k_scale
            sk_l = self._adaptive_k(loser_id, surface) * k_scale

            new_sr_w = sr_w + sk_w * (1.0 - s_exp_w)
            new_sr_l = sr_l + sk_l * (0.0 - (1.0 - s_exp_w))

            self.ratings_surface[(winner_id, surface)] = new_sr_w
            self.ratings_surface[(loser_id, surface)] = new_sr_l
            self.match_counts_surface[(winner_id, surface)] = (
                self.match_counts_surface.get((winner_id, surface), 0) + 1
            )
            self.match_counts_surface[(loser_id, surface)] = (
                self.match_counts_surface.get((loser_id, surface), 0) + 1
            )

            result["winner_elo_surface_before"] = sr_w
            result["loser_elo_surface_before"] = sr_l
            result["winner_elo_surface_after"] = new_sr_w
            result["loser_elo_surface_after"] = new_sr_l
        else:
            result["winner_elo_surface_before"] = self.initial
            result["loser_elo_surface_before"] = self.initial
            result["winner_elo_surface_after"] = self.initial
            result["loser_elo_surface_after"] = self.initial

        # Track last match date for inactivity decay
        if date is not None and not pd.isna(date):
            self.last_date[winner_id] = date
            self.last_date[loser_id] = date

        return result

    def get_rating(self, player_id: int, surface: str | None = None) -> float:
        """Get current rating (before update).

        Falls back to the global rating when the surface is not in the
        configured SURFACES list, so a never-seen surface never silently
        returns the default initial rating instead of real global strength.
        """
        if surface and surface in config.SURFACES:
            return self.ratings_surface.get((player_id, surface), float(self.initial))
        return self.ratings_global.get(player_id, float(self.initial))

    def get_blended_rating(self, player_id: int, surface: str | None = None) -> float:
        """Surface ELO shrunk toward global ELO based on surface experience."""
        r_global = self.get_rating(player_id)
        if not surface or surface not in config.SURFACES:
            return r_global
        r_surf = self.ratings_surface.get((player_id, surface), float(self.initial))
        n_surf = self.match_counts_surface.get((player_id, surface), 0)
        w = n_surf / (n_surf + config.ELO_SURFACE_BLEND_SHRINKAGE)
        return w * r_surf + (1.0 - w) * r_global

    def get_match_count(self, player_id: int, surface: str | None = None) -> int:
        if surface and surface in config.SURFACES:
            return self.match_counts_surface.get((player_id, surface), 0)
        return self.match_counts.get(player_id, 0)
