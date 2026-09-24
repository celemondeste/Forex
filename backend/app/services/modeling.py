import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from hmmlearn import hmm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HmmModel, OhlcBar, Prediction
from app.services.features import FEATURE_COLUMNS, FEATURE_VERSION, build_features

def load_frame(db: Session, pair: str, timeframe: str) -> pd.DataFrame:
    bars = db.scalars(select(OhlcBar).where(OhlcBar.pair == pair,
        OhlcBar.timeframe == timeframe).order_by(OhlcBar.timestamp)).all()
    if len(bars) < 100:
        raise ValueError("At least 100 daily OHLC bars are required")
    return pd.DataFrame([{"timestamp": bar.timestamp, "open": bar.open, "high": bar.high,
        "low": bar.low, "close": bar.close, "volume": bar.volume} for bar in bars]).set_index("timestamp")


def train_candidate(db: Session, pair: str, timeframe: str = "1d") -> dict:
    if timeframe != "1d":
        raise ValueError("The MVP model supports daily bars only")
    frame = load_frame(db, pair, timeframe)
    features = build_features(frame)
    split = int(len(features) * 0.8)
    if split < 50 or len(features) - split < 10:
        raise ValueError("Insufficient rows for a chronological train/validation split")
    mean, std = features.iloc[:split].mean(), features.iloc[:split].std().replace(0, 1)
    train_x = ((features.iloc[:split] - mean) / std).to_numpy()
    valid_x = ((features.iloc[split:] - mean) / std).to_numpy()
    model = hmm.GaussianHMM(n_components=3, covariance_type="diag", n_iter=300,
        random_state=42, min_covar=1e-4)
    model.fit(train_x)
    validation_score = float(model.score(valid_x))
    state_returns = features.iloc[:split].groupby(model.predict(train_x))["log_return"].mean().reindex(range(3))
    if state_returns.isna().any():
        raise ValueError("Training did not identify all three market states")
    rank = state_returns.sort_values().index.tolist()
    state_names = {int(rank[0]): "Bear", int(rank[1]): "Sideways", int(rank[2]): "Bull"}
    version = f"{pair.replace('/', '')}-{timeframe}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    artifact_dir = Path(settings.model_artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{version}.joblib"
    bundle = {"model": model, "mean": mean.to_dict(), "std": std.to_dict(),
        "state_names": state_names, "feature_columns": FEATURE_COLUMNS,
        "feature_version": FEATURE_VERSION}
    joblib.dump(bundle, artifact_path)
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    record = HmmModel(pair=pair, timeframe=timeframe, model_version=version, n_components=3,
        feature_version=FEATURE_VERSION, artifact_uri=str(artifact_path.resolve()), artifact_hash=digest,
        training_window_start=features.index[0], training_window_end=features.index[split - 1],
        framework_version=sklearn.__version__, status="candidate",
        metrics_json={"validation_log_likelihood": validation_score, "validation_rows": len(valid_x),
                      "split": "chronological_80_20", "random_state": 42})
    db.add(record)
    db.commit()
    return {"model_version": version, "status": record.status, "metrics": record.metrics_json}


def predict(db: Session, pair: str, timeframe: str = "1d", persist: bool = False) -> dict:
    record = db.scalar(select(HmmModel).where(HmmModel.pair == pair,
        HmmModel.timeframe == timeframe, HmmModel.status == "approved").order_by(HmmModel.trained_at.desc()))
    if not record:
        raise LookupError("No approved model is available for this pair and timeframe")
    if hashlib.sha256(Path(record.artifact_uri).read_bytes()).hexdigest() != record.artifact_hash:
        raise RuntimeError("Approved model artifact hash does not match the registry")
    bundle = joblib.load(record.artifact_uri)
    frame = load_frame(db, pair, timeframe)
    features = build_features(frame)
    x = ((features - pd.Series(bundle["mean"])) / pd.Series(bundle["std"])).to_numpy()
    estimator = bundle["model"]
    current = estimator.predict_proba(x)[-1]
    next_probs = current @ estimator.transmat_
    mapping = {int(key): value for key, value in bundle["state_names"].items()}
    current_by_name = {mapping[i]: float(current[i]) for i in range(3)}
    next_by_name = {mapping[i]: float(next_probs[i]) for i in range(3)}
    current_state = int(np.argmax(current))
    regime = mapping[current_state]
    signal = "BUY" if regime == "Bull" else "SELL" if regime == "Bear" else "HOLD"
    as_of = frame.index[-1]
    payload = {"pair": pair, "timeframe": timeframe, "as_of_timestamp": as_of,
        "forecast_horizon": "1d", "forecast_for_timestamp": as_of + timedelta(days=1),
        "current_state": current_state, "current_regime": regime,
        "current_probabilities": current_by_name, "next_state_probabilities": next_by_name,
        "signal": signal, "model_version": record.model_version}
    if persist:
        db.add(Prediction(model_id=record.id, pair=pair, timeframe=timeframe,
            as_of_timestamp=payload["as_of_timestamp"], forecast_horizon="1d",
            forecast_for_timestamp=payload["forecast_for_timestamp"], current_state=current_state,
            current_regime=regime, current_probabilities=current_by_name,
            next_state_probabilities=next_by_name, signal=signal))
        db.commit()
    return payload
