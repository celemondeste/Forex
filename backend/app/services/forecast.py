from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HmmModel, OhlcBar
from app.services.market_data import sync_daily_pair
from app.services.modeling import load_approved_bundle, load_frame, train_candidate
from app.services.features import build_features

MINIMUM_BARS = 260
SIMULATIONS = 600
SIMULATION_SEED = 7


def bar_count(db: Session, pair: str, timeframe: str) -> int:
    return int(db.scalar(select(func.count(OhlcBar.id)).where(
        OhlcBar.pair == pair, OhlcBar.timeframe == timeframe)) or 0)


def approved_model(db: Session, pair: str, timeframe: str) -> HmmModel | None:
    return db.scalar(select(HmmModel).where(HmmModel.pair == pair, HmmModel.timeframe == timeframe,
        HmmModel.status == "approved").order_by(HmmModel.trained_at.desc()))


def latest_timestamp(db: Session, pair: str, timeframe: str) -> datetime | None:
    return db.scalar(select(func.max(OhlcBar.timestamp)).where(
        OhlcBar.pair == pair, OhlcBar.timeframe == timeframe))


def prepare_pair(db: Session, pair: str, timeframe: str = "1d") -> dict:
    """Make a searched pair usable: ingest missing history and auto-approve a model when allowed.

    Admin-approved models are never replaced; auto-approved models carry
    `auto_approved` in their metrics so their lineage stays distinguishable.
    """
    steps: list[str] = []
    if timeframe != "1d":
        raise ValueError("The MVP model supports daily bars only")
    if not settings.auto_prepare_pairs:
        return {"steps": steps, "auto_prepared": False}

    stored = bar_count(db, pair, timeframe)
    stale_after = settings.auto_prepare_stale_days
    latest = latest_timestamp(db, pair, timeframe)
    outdated = latest is None or (datetime.now(timezone.utc) - latest.replace(tzinfo=timezone.utc)).days > stale_after
    if stored < MINIMUM_BARS or outdated:
        sync_daily_pair(db, pair, period=settings.auto_prepare_period)
        steps.append("synced")

    if approved_model(db, pair, timeframe) is None:
        candidate = train_candidate(db, pair, timeframe)
        record = db.scalar(select(HmmModel).where(HmmModel.model_version == candidate["model_version"]))
        record.status = "approved"
        record.metrics_json = {**record.metrics_json, "auto_approved": True}
        db.commit()
        steps.append("trained")
    return {"steps": steps, "auto_prepared": bool(steps)}


def future_sessions(last: pd.Timestamp, horizon: int) -> list[pd.Timestamp]:
    return list(pd.bdate_range(start=last + pd.Timedelta(days=1), periods=horizon, tz=last.tz))


def simulate_paths(bundle: dict, posterior: np.ndarray, last_close: float, horizon: int) -> np.ndarray:
    """Monte Carlo price paths from the HMM: sample regimes, then their log-return emissions."""
    estimator = bundle["model"]
    columns = list(bundle["feature_columns"])
    index = columns.index("log_return")
    scale = float(pd.Series(bundle["std"])[columns[index]])
    offset = float(pd.Series(bundle["mean"])[columns[index]])
    means = np.asarray(estimator.means_)[:, index]
    covars = np.asarray(estimator.covars_)
    variances = covars[:, index, index] if covars.ndim == 3 else covars[:, index]
    sigmas = np.sqrt(variances)
    transmat = np.asarray(estimator.transmat_)
    rng = np.random.default_rng(SIMULATION_SEED)

    states = rng.choice(len(means), size=SIMULATIONS, p=posterior)
    log_price = np.full(SIMULATIONS, np.log(last_close))
    paths = np.empty((SIMULATIONS, horizon))
    for step in range(horizon):
        cumulative = np.cumsum(transmat[states], axis=1)
        draws = rng.random((SIMULATIONS, 1))
        states = (draws > cumulative).sum(axis=1).clip(max=len(means) - 1)
        standardized = rng.normal(means[states], sigmas[states])
        log_price = log_price + standardized * scale + offset
        paths[:, step] = log_price
    return np.exp(paths)


def forecast_prices(db: Session, pair: str, timeframe: str = "1d", horizon: int = 30) -> dict:
    record, bundle = load_approved_bundle(db, pair, timeframe)
    frame = load_frame(db, pair, timeframe)
    features = build_features(frame)
    standardized = ((features - pd.Series(bundle["mean"])) / pd.Series(bundle["std"])).to_numpy()
    estimator = bundle["model"]
    posterior = estimator.predict_proba(standardized)[-1]
    posterior = posterior / posterior.sum()
    last_close = float(frame["close"].iloc[-1])
    paths = simulate_paths(bundle, posterior, last_close, horizon)
    dates = future_sessions(pd.Timestamp(frame.index[-1]), horizon)
    median = np.median(paths, axis=0)
    lower = np.quantile(paths, 0.1, axis=0)
    upper = np.quantile(paths, 0.9, axis=0)
    points = [{"timestamp": dates[i].to_pydatetime(), "expected": float(median[i]),
               "lower": float(lower[i]), "upper": float(upper[i])} for i in range(horizon)]
    return {"pair": pair, "timeframe": timeframe, "model_version": record.model_version,
            "as_of_timestamp": pd.Timestamp(frame.index[-1]).to_pydatetime(), "last_close": last_close,
            "horizon_days": horizon, "simulations": SIMULATIONS, "points": points,
            "expected_return": float(median[-1] / last_close - 1)}
