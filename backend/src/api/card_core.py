"""Daily-card prediction core: per-match inference, enrichment and logging.

Split out of api/routes/card.py to respect the 300-line module budget
(AGENT.md). The route module keeps only HTTP concerns; everything here is
purely functional card-building logic.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from logging_config import get_logger
from api.predict_core import predict_with_state, resolve_model_path
from api.schemas import PredictRequest

log = get_logger(__name__)

_SURFACE_HINTS = [
    ("wimbledon", "Grass"),
    ("queen", "Grass"),
    ("halle", "Grass"),
    ("eastbourne", "Grass"),
    ("newport", "Grass"),
    ("stuttgart", "Grass"),
    ("roland garros", "Clay"),
    ("french open", "Clay"),
    ("monte carlo", "Clay"),
    ("madrid", "Clay"),
    ("rome", "Clay"),
    ("hamburg", "Clay"),
    ("bastad", "Clay"),
    ("gstaad", "Clay"),
    ("umag", "Clay"),
    ("kitzbuhel", "Clay"),
    ("cordoba", "Clay"),
    ("buenos aires", "Clay"),
    ("rio", "Clay"),
    ("santiago", "Clay"),
    ("marrakech", "Clay"),
    ("geneva", "Clay"),
    ("lyon", "Clay"),
    ("munich", "Clay"),
    ("estoril", "Clay"),
    ("bucharest", "Clay"),
    ("boerg", "Clay"),
]


def _infer_surface(tournament: str) -> str:
    """Best-effort surface from the tournament name (default Hard)."""
    t = (tournament or "").lower()
    for keyword, surface in _SURFACE_HINTS:
        if keyword in t:
            return surface
    return "Hard"


def resolve_card_model(tour: str) -> tuple[str, Path | None]:
    """Prefer the odds-aware model, fall back to the pure-stats one."""
    model_name = f"{tour}_model_odds.pkl"
    model_path = resolve_model_path(model_name)
    if not model_path.exists():
        model_name = f"{tour}_model.pkl"
        model_path = resolve_model_path(model_name)
    if not model_path.exists():
        return model_name, None
    return model_name, model_path


def _market_edge(
    prob1: float,
    prob2: float,
    o1: float,
    o2: float,
    p1: str,
    p2: str,
    min_edge: float,
) -> tuple[float | None, float | None, dict[str, Any] | None]:
    """Edge vs (vig-normalised) market implied probabilities, plus value-bet flag."""
    raw1, raw2 = 1.0 / o1, 1.0 / o2
    imp1 = raw1 / (raw1 + raw2)
    imp2 = raw2 / (raw1 + raw2)
    edge1 = prob1 - imp1
    edge2 = prob2 - imp2
    value_bet = None
    if edge1 >= min_edge:
        value_bet = {"player": p1, "odds": o1, "edge": round(edge1, 4)}
    elif edge2 >= min_edge:
        value_bet = {"player": p2, "odds": o2, "edge": round(edge2, 4)}
    return edge1, edge2, value_bet


def build_card_predictions(
    bundle: Any,
    state: Any,
    matches: list[dict[str, Any]],
    model_name: str,
    min_edge: float,
    limit: int,
) -> list[dict[str, Any]]:
    """Run tracker-state inference for every match in the cached live feed."""
    predictions: list[dict[str, Any]] = []
    for m in matches[: max(1, int(limit))]:
        p1 = str(m.get("player1", "")).strip()
        p2 = str(m.get("player2", "")).strip()
        if not p1 or not p2:
            continue
        surface = _infer_surface(m.get("tournament", ""))
        best = m.get("best_odds", {}) or {}
        o1 = best.get("player1")
        o2 = best.get("player2")
        o1 = float(o1) if o1 and o1 > 1 else None
        o2 = float(o2) if o2 and o2 > 1 else None
        req = PredictRequest(
            player1=p1,
            player2=p2,
            surface=surface,
            model=model_name,
            best_of=3,
            odds1=o1,
            odds2=o2,
        )
        try:
            res = predict_with_state(bundle, state, req)
        except Exception as e:  # noqa: BLE001
            res = {"error": str(e)}
        if "error" in res:
            predictions.append(
                {
                    "match": f"{p1} vs {p2}",
                    "tournament": m.get("tournament", ""),
                    "surface": surface,
                    "commence_time": m.get("commence_time", ""),
                    "error": res["error"],
                }
            )
            continue
        prob1 = float(res["prob1"])
        prob2 = float(res["prob2"])
        edge1 = None
        edge2 = None
        value_bet = None
        if o1 and o2 and o1 > 1 and o2 > 1:
            edge1, edge2, value_bet = _market_edge(
                prob1, prob2, o1, o2, p1, p2, min_edge
            )
        predictions.append(
            {
                "match": f"{p1} vs {p2}",
                "player1": p1,
                "player2": p2,
                "tournament": m.get("tournament", ""),
                "surface": surface,
                "commence_time": m.get("commence_time", ""),
                "prob1": prob1,
                "prob2": prob2,
                "winner": res.get("winner"),
                "reliability": res.get("reliability", "bassa"),
                "odds1": o1,
                "odds2": o2,
                "edge1": round(edge1, 4) if edge1 is not None else None,
                "edge2": round(edge2, 4) if edge2 is not None else None,
                "value_bet": value_bet,
            }
        )
    return predictions


def _weather_for(p: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from features.weather import get_live_weather

        w = get_live_weather(
            p.get("tournament", ""),
            (p.get("commence_time") or "")[:10] or None,
        )
        if not w:
            return None
        return {
            "temperature_c": w.get("temperature_c"),
            "humidity_pct": w.get("humidity_pct"),
            "rain_probability": w.get("rain_probability"),
            "wind_speed_kmh": w.get("wind_speed_kmh"),
        }
    except Exception as e:  # noqa: BLE001
        log.debug("Weather enrich failed: %s", e)
        return None


def _ctx_for(p: dict[str, Any], tour: str) -> dict[str, Any] | None:
    if not p.get("player1") or not p.get("player2"):
        return None
    try:
        from features.player_context import player_context

        c1 = player_context(tour, p["player1"])
        c2 = player_context(tour, p["player2"])
        if not c1 and not c2:
            return None
        return {
            "p1_rank": c1.get("rank"),
            "p2_rank": c2.get("rank"),
            "p1_form": c1.get("form"),
            "p2_form": c2.get("form"),
            "p1_ret": c1.get("ret"),
            "p2_ret": c2.get("ret"),
            "p1_age": c1.get("age"),
            "p2_age": c2.get("age"),
            "p1_last_match_date": c1.get("last_match_date"),
            "p2_last_match_date": c2.get("last_match_date"),
        }
    except Exception as e:  # noqa: BLE001
        log.debug("Player-context enrich failed: %s", e)
        return None


def enrich_card_predictions(
    predictions: list[dict[str, Any]], tour: str = "atp"
) -> None:
    """Attach weather + player context to every card prediction in place.

    Weather comes from open-meteo (free, no key) and player context (rank,
    age, recent form, retirement marks) from the local Sackmann CSVs, so the
    whole enrichment is zero-cost and silent on failure. Network-bound work
    runs in a small thread pool so a 20-match card finishes in ~1s.

    Player-news context (injuries, coach change from news articles) is NOT
    included here: the GPT Researcher pipeline is multi-second per match and
    incurs LLM cost. Per-match news is still available via the manual Player
    News Research panel on the Live Market page.
    """
    if not predictions:
        return

    valid = [p for p in predictions if not p.get("error")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for p, w, c in zip(
            valid,
            pool.map(_weather_for, valid),
            pool.map(lambda q: _ctx_for(q, tour), valid),
        ):
            if w:
                p["weather"] = w
            if c:
                p["context"] = c


def log_card_predictions(
    tour: str, model_name: str, predictions: list[dict[str, Any]]
) -> int:
    """Append card predictions to the Track Record, skipping duplicates.

    A prediction already present with the same player pair, surface,
    probability and odds is not re-logged, so regenerating the same card is
    idempotent while price/probability moves still produce new entries.
    """
    from pipeline.track import log_prediction, read_log

    existing = {
        (
            str(r.get("player1")),
            str(r.get("player2")),
            str(r.get("surface")),
            r.get("prob1"),
            r.get("odds1"),
            r.get("odds2"),
        )
        for r in read_log(tour)
    }
    n_logged = 0
    for p in predictions:
        if p.get("error") or p.get("prob1") is None:
            continue
        key = (
            p["player1"],
            p["player2"],
            p["surface"],
            round(float(p["prob1"]), 4),
            p.get("odds1"),
            p.get("odds2"),
        )
        if key in existing:
            continue
        try:
            log_prediction(
                tour=tour,
                model=model_name,
                player1=p["player1"],
                player2=p["player2"],
                surface=p["surface"],
                best_of=3,
                prob1=float(p["prob1"]),
                predicted_winner=p["winner"],
                reliability=p.get("reliability"),
                odds1=p.get("odds1"),
                odds2=p.get("odds2"),
            )
            existing.add(key)
            n_logged += 1
        except Exception as exc:
            log.warning("card log skipped: %s", exc)
    return n_logged
