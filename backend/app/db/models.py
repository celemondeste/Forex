from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OhlcBar(Base):
    __tablename__ = "forex_ohlc"
    __table_args__ = (UniqueConstraint("pair", "timeframe", "timestamp", name="uq_ohlc_pair_tf_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)


class HmmModel(Base):
    __tablename__ = "hmm_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    model_version: Mapped[str] = mapped_column(String(64), unique=True)
    n_components: Mapped[int] = mapped_column(Integer)
    feature_version: Mapped[str] = mapped_column(String(32))
    artifact_uri: Mapped[str] = mapped_column(String(512))
    artifact_hash: Mapped[str] = mapped_column(String(64))
    training_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    framework_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="candidate", index=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("hmm_models.id"), index=True)
    pair: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forecast_horizon: Mapped[str] = mapped_column(String(8))
    forecast_for_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_state: Mapped[int] = mapped_column(Integer)
    current_regime: Mapped[str] = mapped_column(String(16))
    current_probabilities: Mapped[dict] = mapped_column(JSON)
    next_state_probabilities: Mapped[dict] = mapped_column(JSON)
    signal: Mapped[str] = mapped_column(String(8))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DataSyncRun(Base):
    __tablename__ = "data_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pair: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
