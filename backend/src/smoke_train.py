"""End-to-end training smoke test with synthetic data.

This script validates that the entire pipeline works after the v2.1
hardening changes WITHOUT requiring real Jeff Sackmann data.

It:
  1. Generates a synthetic dataset shaped like atp_features.parquet
  2. Runs the full training pipeline (walk-forward OOF, stacking,
     Platt calibration, evaluation)
  3. Verifies the trained bundle has continuous (not binary)
     probabilities

Usage:
    python smoke_train.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def make_synthetic_dataset(n: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic dataset that mimics the feature shape."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "match_id": [f"{i}_A" if i % 2 == 0 else f"{i}_B" for i in range(n)],
            "tourney_date": pd.to_datetime("2020-01-01")
            + pd.to_timedelta(rng.integers(0, 1500, size=n), unit="D"),
            "tourney_name": rng.choice(
                ["Australian Open", "Roland Garros", "Wimbledon"], size=n
            ),
            "surface": rng.choice(["Hard", "Clay", "Grass"], size=n),
            "year": 2020 + rng.integers(0, 5, size=n),
            "p1_name": rng.choice(
                ["Sinner", "Alcaraz", "Djokovic", "Medvedev"], size=n
            ),
            "p2_name": rng.choice(["Zverev", "Rublev", "Rune", "Ruud"], size=n),
            "label": rng.integers(0, 2, size=n),
        }
    )
    # Generate plausible numeric features (37 of them)
    feature_names = [
        "ranking_diff",
        "ranking_points_diff",
        "elo_diff",
        "elo_surface_diff",
        "age_diff",
        "height_diff",
        "hand_matchup",
        "home_country_flag",
        "qualifier_flag_diff",
        "h2h_win_pct",
        "h2h_win_pct_surface",
        "days_rest_diff",
        "matches_last_7_days_diff",
        "ace_pct_diff",
        "df_pct_diff",
        "first_serve_in_pct_diff",
        "win_on_1st_serve_pct_diff",
        "win_on_2nd_serve_pct_diff",
        "bp_saved_pct_diff",
        "bp_converted_pct_diff",
        "first_serve_return_pts_won_pct_diff",
        "second_serve_return_pts_won_pct_diff",
        "return_games_won_pct_diff",
        "win_pct_surface_diff",
        "win_pct_last_10_diff",
        "tiebreak_win_pct_diff",
        "first_set_win_rate_diff",
        "sos_last_10_diff",
        "service_games_won_pct_diff",
        "surface_Hard",
        "surface_Clay",
        "surface_Grass",
        "tourney_level_encoded",
        "round_encoded",
        "best_of",
        "indoor_outdoor",
        "month",
    ]
    for name in feature_names:
        df[name] = rng.normal(0, 1, size=n).astype(float)
    df["surface_Hard"] = (df["surface"] == "Hard").astype(int)
    df["surface_Clay"] = (df["surface"] == "Clay").astype(int)
    df["surface_Grass"] = (df["surface"] == "Grass").astype(int)
    return df


def main() -> int:
    print("=" * 60)
    print(" TENNISBOT END-TO-END TRAINING SMOKE TEST")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_path = tmp_path / "atp_features.parquet"

        print("\n[1/4] Generating synthetic dataset ...")
        df = make_synthetic_dataset(n=5000)
        df.to_parquet(data_path)
        print(f"  Saved to {data_path}")

        # Patch config paths to point at the temp dir
        import config

        config.PROCESSED_DIR = tmp_path
        config.MODELS_DIR = tmp_path
        config.REPORTS_DIR = tmp_path
        # Reduce Optuna trials for speed
        from pipeline import training

        print("\n[2/4] Running training pipeline (5 Optuna trials per fold) ...")
        result = training.train_pipeline(
            tour="atp",
            n_optuna_trials=5,
        )
        bundle = result["model_bundle"]

        # The training.py saves to MODELS_DIR/{tour}_stacking_model.pkl
        actual_model_path = tmp_path / "atp_stacking_model.pkl"
        if not actual_model_path.exists():
            print(f"  FAIL: model not saved at {actual_model_path}")
            return 1
        print(f"  Saved model to {actual_model_path}")

        print("\n[3/4] Validating model bundle ...")
        bundle = joblib.load(actual_model_path)
        required = [
            "base_models",
            "meta_model",
            "calibrator",
            "imputer",
            "scaler",
            "feature_cols",
        ]
        for key in required:
            if key not in bundle:
                print(f"  FAIL: bundle missing key '{key}'")
                return 1
        print(f"  Bundle keys OK: {list(bundle.keys())}")
        print(f"  Feature columns: {len(bundle['feature_cols'])}")
        print(f"  Calibrator method: {bundle['calibrator'].method}")

        print("\n[4/4] Validating calibration produces continuous probabilities ...")
        cal = bundle["calibrator"]
        # Build a small synthetic X to verify
        rng = np.random.default_rng(0)
        X = rng.normal(0, 1, size=(100, len(bundle["feature_cols"])))
        X_imp = bundle["imputer"].transform(X)
        X_scaled = bundle["scaler"].transform(X_imp)
        p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_scaled)[:, 1]
        p_xgb = bundle["base_models"]["xgb"].predict_proba(X_scaled)[:, 1]
        p_lr = bundle["base_models"]["lr"].predict_proba(X_scaled)[:, 1]
        X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
        raw = bundle["meta_model"].predict_proba(X_meta)[:, 1]
        calibrated = cal.predict(raw)
        # Test: probabilities must be CONTINUOUS (not just 0 or 1)
        n_unique = len(np.unique(calibrated))
        n_in_range = np.sum((calibrated >= 0.0) & (calibrated <= 1.0))
        print(
            f"  Raw probabilities:     unique={len(np.unique(raw))}, in [0,1]={np.sum((raw>=0)&(raw<=1))}/{len(raw)}"
        )
        print(
            f"  Calibrated probs:      unique={n_unique}, in [0,1]={n_in_range}/{len(calibrated)}"
        )
        if n_unique < 5:
            print(f"  FAIL: calibrator output has only {n_unique} unique values")
            print(f"  Sample values: {calibrated[:10]}")
            return 1
        if n_in_range != len(calibrated):
            print("  FAIL: some calibrated values outside [0, 1]")
            return 1
        print(f"  PASS: {n_unique} unique calibrated probabilities, all in [0, 1]")

    print("\n" + "=" * 60)
    print(" ALL CHECKS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
