from datetime import datetime, timezone
from math import isfinite

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DataSyncRun, OhlcBar

TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"


def fetch_daily_bars(pair: str, outputsize: int = 5000) -> list[dict]:
    """Fetch daily OHLC bars for a pair like 'EUR/USD' from Twelve Data (oldest first)."""
    if not settings.twelve_data_api_key:
        raise ValueError("TWELVE_DATA_API_KEY is not configured")
    response = requests.get(
        TWELVE_DATA_URL,
        params={
            "symbol": pair,  # Twelve Data uses the same EUR/USD format as this project
            "interval": "1day",
            "outputsize": outputsize,  # 1..5000
            "timezone": "UTC",
            "apikey": settings.twelve_data_api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "error":
        raise ValueError(f"Twelve Data error {data.get('code')}: {data.get('message')}")
    values = data.get("values") or []
    if not values:
        raise ValueError("Twelve Data returned no daily bars")
    return sorted(values, key=lambda item: item["datetime"])


def sync_daily_pair(db: Session, pair: str, outputsize: int = 5000) -> dict:
    run = DataSyncRun(pair=pair, timeframe="1d")
    db.add(run)
    db.flush()
    try:
        bars = fetch_daily_bars(pair, outputsize)
        today = datetime.now(timezone.utc).date()
        # Providers can return the same daily timestamp more than once. Keep the
        # last valid bar so one sync never queues duplicate unique keys.
        cleaned_by_timestamp: dict[datetime, dict] = {}
        for item in bars:
            stamp = datetime.fromisoformat(item["datetime"]).replace(tzinfo=timezone.utc)
            if stamp.date() >= today:
                continue  # skip today's bar: it is still forming
            try:
                values = {key: float(item[key]) for key in ("open", "high", "low", "close")}
            except (KeyError, TypeError, ValueError):
                continue
            if any(not isfinite(value) or value <= 0 for value in values.values()):
                continue
            # same sanity check as before: high/low must bracket open and close
            if values["high"] < max(values["open"], values["close"], values["low"]):
                continue
            if values["low"] > min(values["open"], values["close"], values["high"]):
                continue
            values["volume"] = None  # forex has no meaningful volume
            cleaned_by_timestamp[stamp] = values

        if not cleaned_by_timestamp:
            raise ValueError("No valid daily bars after validation")

        run.rows_fetched = len(cleaned_by_timestamp)
        for stamp, values in sorted(cleaned_by_timestamp.items()):
            existing = db.scalar(select(OhlcBar).where(OhlcBar.pair == pair,
                OhlcBar.timeframe == "1d", OhlcBar.timestamp == stamp))
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
