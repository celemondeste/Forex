from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str


class MarketBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class MarketResponse(BaseModel):
    pair: str
    timeframe: str
    bars: list[MarketBar]
    as_of_timestamp: datetime | None
    stale: bool


class ModelResponse(BaseModel):
    model_version: str
    pair: str
    timeframe: str
    status: str
    feature_version: str
    artifact_hash: str
    trained_at: datetime
    metrics: dict


class PredictionResponse(BaseModel):
    pair: str
    timeframe: str
    as_of_timestamp: datetime
    forecast_horizon: str
    forecast_for_timestamp: datetime
    current_state: int
    current_regime: str
    current_probabilities: dict[str, float]
    next_state_probabilities: dict[str, float]
    signal: Literal["BUY", "HOLD", "SELL"]
    model_version: str
