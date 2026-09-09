"""Training control routes: status, start, reload."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from config import SRC_DIR
from logging_config import get_logger
from api.schemas import TrainRequest
from api.state import invalidate_caches, training_status

log = get_logger(__name__)

router = APIRouter()


def run_training_pipeline(
    tour: str, trials: int, start_year: int, end_year: int
) -> None:
    """Launch main.py train in background and capture logs."""
    training_status["is_training"] = True
    training_status["error"] = False
    training_status["success"] = False
    training_status["current_task"] = (
        f"Training ensemble for tour {tour.upper()} ({start_year}-{end_year})"
    )
    training_status["logs"] = []

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "main.py",
                "train",
                "--tour",
                tour,
                "--optuna-trials",
                str(trials),
                "--start-year",
                str(start_year),
                "--end-year",
                str(end_year),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(SRC_DIR),
        )
        if process.stdout is None:
            raise RuntimeError("Failed to capture training subprocess stdout")

        for line in iter(process.stdout.readline, ""):
            if line:
                training_status["logs"].append(line.strip())
                if len(training_status["logs"]) > 1500:
                    training_status["logs"].pop(0)

        process.stdout.close()
        process.wait()

        if process.returncode == 0:
            training_status["current_task"] = "Training Completato!"
            training_status["success"] = True
            invalidate_caches()
        else:
            training_status["current_task"] = (
                f"Errore! (Exit code: {process.returncode})"
            )
            training_status["error"] = True

    except Exception as e:
        training_status["current_task"] = f"Exception: {str(e)}"
        training_status["error"] = True
    finally:
        training_status["is_training"] = False


@router.get("/api/status")
def get_status() -> dict[str, Any]:
    return training_status


@router.post("/api/train/start")
def start_training(
    req: TrainRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    if training_status["is_training"]:
        raise HTTPException(status_code=400, detail="Training already running")
    background_tasks.add_task(
        run_training_pipeline, req.tour, req.trials, req.startYear, req.endYear
    )
    return {
        "message": (
            f"Training started per tour {req.tour} iterazioni {req.trials} "
            f"anni {req.startYear}-{req.endYear}"
        )
    }


@router.post("/api/reload")
def reload_dataset() -> dict[str, Any]:
    invalidate_caches()
    return {"message": "Cache dataset e inference state invalidata."}
