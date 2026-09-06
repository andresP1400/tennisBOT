"""Custom exceptions for tennisBOT domain.

Use these instead of bare `raise Exception(...)` so callers can handle
specific failure modes without catching everything.
"""

from __future__ import annotations


class TennisBotError(Exception):
    """Base class for all tennisBOT errors."""


class DataNotFoundError(TennisBotError):
    """Raised when a required dataset file (parquet, csv) is missing."""


class ModelNotFoundError(TennisBotError):
    """Raised when a model .pkl file is missing or invalid."""


class FeatureEngineeringError(TennisBotError):
    """Raised when feature engineering fails (missing columns, etc.)."""


class TrainingError(TennisBotError):
    """Raised when the training pipeline fails (no usable folds, etc.)."""


class PredictionError(TennisBotError):
    """Raised when inference fails (imputer/scaler missing, etc.)."""


class ExternalAPIError(TennisBotError):
    """Raised when an external API (TheOddsAPI, Open-Meteo) fails."""

    def __init__(
        self, service: str, message: str, status_code: int | None = None
    ) -> None:
        super().__init__(
            f"[{service}] {message}"
            + (f" (status={status_code})" if status_code else "")
        )
        self.service = service
        self.status_code = status_code
