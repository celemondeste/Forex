from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataSyncRun, OhlcBar


def yahoo_ticker(pair: str) -> str:
    return pair.replace("/", "") + "=X"


def sync_daily_pair(db: Session, pair: str, period: str = "10y") -> dict:
    run = DataSyncRun(pair=pair, timeframe="1d")
    db.add(run)
    db.flush()
    try:
        raw = yf.download(yahoo_ticker(pair), period=period, interval="1d", auto_adjust=False, progress=False)
        if raw.empty:
            raise ValueError("Yahoo Finance returned no daily bars")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [str(column).lower() for column in raw.columns]
        required = {"open", "high", "low", "close"}
        if not required.issubset(raw.columns):
            raise ValueError("Yahoo Finance response is missing OHLC columns")
        raw = raw.dropna(subset=list(required))
        raw = raw[(raw["high"] >= raw[["open", "close", "low"]].max(axis=1)) &
                  (raw["low"] <= raw[["open", "close", "high"]].min(axis=1))]
        raw = raw[~raw.index.duplicated(keep="last")]
        run.rows_fetched = len(raw)
        for date, row in raw.iterrows():
            stamp_value = pd.Timestamp(date)
            stamp = (stamp_value.tz_localize("UTC") if stamp_value.tzinfo is None
                     else stamp_value.tz_convert("UTC")).to_pydatetime()
            existing = db.scalar(select(OhlcBar).where(OhlcBar.pair == pair,
                OhlcBar.timeframe == "1d", OhlcBar.timestamp == stamp))
            values = {key: float(row[key]) for key in required}
            volume = row.get("volume")
            values["volume"] = None if pd.isna(volume) else float(volume)
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                run.rows_updated += 1
            else:
                db.add(OhlcBar(pair=pair, timeframe="1d", timestamp=stamp, **values))
                run.rows_inserted += 1
        run.status = "complete"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"run_id": run.id, "status": run.status, "rows_fetched": run.rows_fetched,
                "rows_inserted": run.rows_inserted, "rows_updated": run.rows_updated}
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_summary = str(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        raise
