"""Pydantic request models shared by the API route modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrainRequest(BaseModel):
    tour: str = Field(..., pattern="^(atp|wta)$")
    trials: int = Field(..., ge=1, le=1000)
    startYear: int = Field(..., ge=1968, le=2100)
    endYear: int = Field(..., ge=1968, le=2100)


class PredictRequest(BaseModel):
    player1: str = Field(..., min_length=1, max_length=128)
    player2: str = Field(..., min_length=1, max_length=128)
    surface: str = Field(..., min_length=1, max_length=32)
    model: str = Field(..., min_length=1, max_length=128)
    best_of: int = Field(default=3, ge=3, le=5)
    odds1: float | None = Field(default=None, gt=1.0)
    odds2: float | None = Field(default=None, gt=1.0)


class LiveOddsRequest(BaseModel):
    player1: str
    player2: str
    surface: str | None = None


class ValueBetRequest(BaseModel):
    player1: str = Field(..., min_length=1, max_length=128)
    player2: str = Field(..., min_length=1, max_length=128)
    surface: str | None = Field(default=None, max_length=32)
    model_prob1: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str = Field(default="atp_stacking_model.pkl", max_length=128)
    min_edge: float = Field(default=0.05, ge=0.0, le=1.0)


class PlayerNewsRequest(BaseModel):
    player1: str
    player2: str
    surface: str | None = None
