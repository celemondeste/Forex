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


class ForecastPoint(BaseModel):
    timestamp: datetime
    expected: float
    lower: float
    upper: float


class ForecastResponse(BaseModel):
    pair: str
    timeframe: str
    model_version: str
    as_of_timestamp: datetime
    last_close: float
    horizon_days: int
    simulations: int
    expected_return: float
    points: list[ForecastPoint]


class CurrencyPair(BaseModel):
    pair: str
    symbol: str
    label: str


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


class SearchResponse(BaseModel):
    pair: str
    timeframe: str
    bars: list[MarketBar]
    as_of_timestamp: datetime | None
    stale: bool
    prepared_steps: list[str]
    prediction: PredictionResponse | None = None
    forecast: ForecastResponse | None = None
    model: ModelResponse | None = None
