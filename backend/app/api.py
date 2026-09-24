from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HmmModel, OhlcBar
from app.db.session import get_db
from app.schemas import (CurrencyPair, ForecastResponse, HealthResponse, MarketResponse,
                         ModelResponse, PredictionResponse, SearchResponse)
from app.services import currencies
from app.services.forecast import forecast_prices, prepare_pair
from app.services.market_data import sync_daily_pair
from app.services.modeling import predict, train_candidate

router = APIRouter(prefix="/api")


def normalize_pair(pair: str) -> str:
    value = pair.upper().replace("_", "/").replace("-", "/")
    if "/" not in value and len(value) == 6:
        value = value[:3] + "/" + value[3:]
    if len(value) != 7 or value[3] != "/" or not value.replace("/", "").isalpha():
        raise HTTPException(422, "Pair must look like EUR/USD")
    return value


def require_admin(x_admin_key: str | None):
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(401, "Valid X-Admin-Key header required")


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc


@router.get("/market/{pair}", response_model=MarketResponse)
def market(pair: str, timeframe: str = Query("1d", pattern="^1d$"), limit: int = Query(500, ge=1, le=5000), db: Session = Depends(get_db)):
    return market_payload(db, normalize_pair(pair), timeframe, limit)


def market_payload(db: Session, pair: str, timeframe: str, limit: int) -> dict:
    bars = db.query(OhlcBar).filter_by(pair=pair, timeframe=timeframe).order_by(OhlcBar.timestamp.desc()).limit(limit).all()
    bars.reverse()
    latest = bars[-1].timestamp if bars else None
    stale = latest is None or (datetime.now(timezone.utc) - latest.replace(tzinfo=timezone.utc)).days > 4
    return {"pair": pair, "timeframe": timeframe, "bars": bars, "as_of_timestamp": latest, "stale": stale}


def model_payload(db: Session, pair: str, timeframe: str) -> dict | None:
    model = db.query(HmmModel).filter_by(pair=pair, timeframe=timeframe, status="approved").order_by(HmmModel.trained_at.desc()).first()
    if not model:
        return None
    return {"model_version": model.model_version, "pair": pair, "timeframe": timeframe,
        "status": model.status, "feature_version": model.feature_version,
        "artifact_hash": model.artifact_hash, "trained_at": model.trained_at,
        "metrics": model.metrics_json}


@router.get("/models/{pair}", response_model=ModelResponse)
def model_metadata(pair: str, timeframe: str = Query("1d", pattern="^1d$"), db: Session = Depends(get_db)):
    payload = model_payload(db, normalize_pair(pair), timeframe)
    if not payload:
        raise HTTPException(404, "No approved model is available")
    return payload


@router.get("/currencies", response_model=list[CurrencyPair])
def currency_search(q: str = Query("", max_length=32), limit: int = Query(12, ge=1, le=50)):
    return currencies.search(q, limit)


@router.get("/forecast/{pair}", response_model=ForecastResponse)
def forecast(pair: str, timeframe: str = Query("1d", pattern="^1d$"),
             horizon: int = Query(settings.forecast_horizon_days, ge=1, le=180),
             db: Session = Depends(get_db)):
    try:
        return forecast_prices(db, normalize_pair(pair), timeframe, horizon)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/search/{pair}", response_model=SearchResponse)
def search(pair: str, timeframe: str = Query("1d", pattern="^1d$"),
           limit: int = Query(250, ge=1, le=5000),
           horizon: int = Query(settings.forecast_horizon_days, ge=1, le=180),
           db: Session = Depends(get_db)):
    """One call behind the search box: ingest and train on demand, then return history and forecast."""
    pair = normalize_pair(pair)
    try:
        prepared = prepare_pair(db, pair, timeframe)
    except Exception as exc:
        raise HTTPException(502, f"Could not prepare {pair}: {exc}") from exc

    payload = market_payload(db, pair, timeframe, limit)
    if not payload["bars"]:
        raise HTTPException(404, f"No daily history is available for {pair}")
    payload["prepared_steps"] = prepared["steps"]
    payload["model"] = model_payload(db, pair, timeframe)
    try:
        payload["prediction"] = predict(db, pair, timeframe)
        payload["forecast"] = forecast_prices(db, pair, timeframe, horizon)
    except (LookupError, ValueError, RuntimeError):
        payload["prediction"] = None
        payload["forecast"] = None
    return payload


@router.get("/predictions/{pair}", response_model=PredictionResponse)
def prediction(pair: str, timeframe: str = Query("1d", pattern="^1d$"), db: Session = Depends(get_db)):
    try:
        return predict(db, normalize_pair(pair), timeframe)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/admin/sync/{pair}")
def sync(pair: str, x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    require_admin(x_admin_key)
    try:
        return sync_daily_pair(db, normalize_pair(pair))
    except Exception as exc:
        raise HTTPException(502, f"Market data sync failed: {exc}") from exc


@router.post("/admin/train/{pair}")
def train(pair: str, x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    require_admin(x_admin_key)
    try:
        return train_candidate(db, normalize_pair(pair))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/admin/predict/{pair}", response_model=PredictionResponse)
def create_prediction(pair: str, x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    require_admin(x_admin_key)
    try:
        return predict(db, normalize_pair(pair), persist=True)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/admin/models/{model_version}/approve")
def approve(model_version: str, x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    require_admin(x_admin_key)
    record = db.query(HmmModel).filter_by(model_version=model_version).first()
    if not record or record.status != "candidate":
        raise HTTPException(404, "Candidate model not found")
    db.query(HmmModel).filter_by(pair=record.pair, timeframe=record.timeframe, status="approved").update({"status": "retired"})
    record.status = "approved"
    db.commit()
    return {"model_version": model_version, "status": record.status}
