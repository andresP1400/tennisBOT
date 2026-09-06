"""Track Record routes: read, settle, verify and match history."""

from __future__ import annotations

from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter

from config import BASE_DIR
from api.predict_core import resolve_model_path

router = APIRouter()


@router.get("/api/track")
def get_track(tour: str = "atp", limit: int = 500) -> dict[str, Any]:
    try:
        from pipeline.track import read_log, summary

        records = read_log(tour)
        records = sorted(records, key=lambda r: r.get("ts", ""), reverse=True)[:limit]
        return {"summary": summary(tour), "records": records}
    except Exception as e:
        return {"error": str(e), "summary": {}, "records": []}


@router.post("/api/track/settle")
def settle_track(tour: str = "atp") -> dict[str, Any]:
    try:
        from pipeline.track import settle_predictions

        return settle_predictions(tour)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/track/verify")
def verify_track(tour: str = "atp") -> dict[str, Any]:
    try:
        from pipeline.track import verify_integrity

        return verify_integrity(tour)
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/history")
def get_match_history(limit: int = 200) -> dict[str, Any]:
    try:
        for name in ("atp_stacking_model.pkl", "atp_model.pkl"):
            model_path = resolve_model_path(name)
            if model_path.exists():
                break
        else:
            return {"error": "Modello non trovato in models/"}

        bundle = joblib.load(model_path)
        data_path = BASE_DIR / "data" / "processed" / "atp_features.parquet"
        if not data_path.exists():
            return {
                "error": "atp_features.parquet non trovato. Addestrare prima il modello!"
            }

        df = pd.read_parquet(data_path)
        df = df[~df["tourney_name"].str.contains("Next Gen", na=False)]
        try:
            base_ids = df["match_id"].str.split("_").str[0].astype(int)
        except ValueError:
            base_ids = pd.Series(range(len(df)))

        keep_a = (base_ids % 2 == 0) & df["match_id"].str.endswith("_A", na=False)
        keep_b = (base_ids % 2 != 0) & df["match_id"].str.endswith("_B", na=False)
        df_single = df[keep_a | keep_b].copy()
        sort_col = (
            "match_date_est"
            if "match_date_est" in df_single.columns
            else "tourney_date"
        )
        # Fetch enough rows for the requested limit (no artificial 100-row ceiling)
        take = max(int(limit), 1)
        df_single = df_single.sort_values(sort_col, ascending=False).head(take)

        feature_cols = bundle["feature_cols"]
        # Only use columns that exist
        available = [c for c in feature_cols if c in df_single.columns]
        X = df_single[available].reindex(columns=feature_cols).values
        X_imp = bundle["imputer"].transform(X)
        X_scaled = bundle["scaler"].transform(X_imp)
        p_lgbm = bundle["base_models"]["lgbm"].predict_proba(X_scaled)[:, 1]
        p_xgb = bundle["base_models"]["xgb"].predict_proba(X_scaled)[:, 1]
        p_lr = bundle["base_models"]["lr"].predict_proba(X_scaled)[:, 1]
        X_meta = np.column_stack([p_lgbm, p_xgb, p_lr])
        raw_probs = bundle["meta_model"].predict_proba(X_meta)[:, 1]
        if bundle.get("calibrator") is not None:
            final_probs = bundle["calibrator"].predict(raw_probs.reshape(-1, 1))
        else:
            final_probs = raw_probs

        results = []
        for i, row in enumerate(df_single.itertuples()):
            prob1 = float(final_probs[i])
            actual_winner = row.p1_name if row.label == 1 else row.p2_name
            d_str = str(getattr(row, "tourney_date", ""))[:10]
            results.append(
                {
                    "id": str(row.match_id),
                    "date": d_str,
                    "tournament": str(row.tourney_name),
                    "surface": str(row.surface),
                    "player1": str(row.p1_name),
                    "player2": str(row.p2_name),
                    "prob1": prob1,
                    "prob2": 1.0 - prob1,
                    "winner": actual_winner,
                }
            )
        return {"matches": results[:limit]}
    except Exception as e:
        return {"error": str(e)}
