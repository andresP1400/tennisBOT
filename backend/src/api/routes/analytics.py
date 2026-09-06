"""Evaluation analytics routes: metrics CSV and chart PNGs."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from config import REPORTS_DIR

router = APIRouter()

_CHART_FILES = [
    {"name": "ROC Curve", "file": "1_roc_curve.png"},
    {"name": "Calibration Curve", "file": "2_calibration_curve.png"},
    {"name": "Feature Importance", "file": "3_feature_importance.png"},
    {"name": "SHAP Summary", "file": "4_shap_summary.png"},
    {"name": "Brier Monthly", "file": "5_brier_monthly.png"},
]
_CHART_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+\.png$")
_VALID_TOURS = ("atp", "wta", "atp_odds", "wta_odds")


@router.get("/api/metrics")
def get_metrics(tour: str = "atp") -> Response:
    if tour not in _VALID_TOURS:
        raise HTTPException(status_code=400, detail="Invalid tour")
    metrics_path = REPORTS_DIR / tour / "metrics_summary.csv"
    if not metrics_path.exists():
        return Response(content="metric,test,val\n", media_type="text/csv")
    return Response(
        content=metrics_path.read_text(encoding="utf-8"),
        media_type="text/csv",
    )


@router.get("/api/charts")
def list_charts(tour: str = "atp") -> dict[str, Any]:
    """List evaluation chart PNGs for a tour (used by dashboard / reports)."""
    if tour not in _VALID_TOURS:
        raise HTTPException(status_code=400, detail="Invalid tour")
    tour_dir = REPORTS_DIR / tour
    charts = []
    for c in _CHART_FILES:
        path = tour_dir / c["file"]
        charts.append(
            {
                "name": c["name"],
                "file": c["file"],
                "exists": path.is_file(),
            }
        )
    return {"tour": tour, "charts": charts}


@router.get("/api/charts/{name}")
def get_chart(name: str, tour: str = "atp") -> Response:
    """Serve a single evaluation chart PNG from reports/{tour}/."""
    if tour not in _VALID_TOURS:
        raise HTTPException(status_code=400, detail="Invalid tour")
    if not _CHART_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid chart name")
    tour_dir = (REPORTS_DIR / tour).resolve()
    file_path = (tour_dir / name).resolve()
    if not str(file_path).startswith(str(tour_dir)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Chart not found")
    return Response(
        content=file_path.read_bytes(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=60"},
    )
