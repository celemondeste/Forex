"""Auto-update: keeps every pair stored in the database fresh, from inside the backend.

Save as backend/app/services/scheduler.py
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models import OhlcBar
from app.db.session import get_db
from app.services.market_data import sync_daily_pair
from app.services.modeling import predict

log = logging.getLogger("uvicorn.error")  # shows up in the normal uvicorn console output
_task: asyncio.Task | None = None

PAUSE_BETWEEN_PAIRS = 10   # Twelve Data free plan: 8 requests per minute
INCREMENTAL_BARS = 30      # a daily refresh only needs the latest bars, not 5000


def _enabled() -> bool:
    return bool(getattr(settings, "auto_update_enabled", True))


def _run_hour_utc() -> int:
    return int(getattr(settings, "auto_update_hour_utc", 1))


def _seconds_until_next_run() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=_run_hour_utc(), minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_update_once() -> dict:
    """Blocking. Refresh every pair already in the database that is out of date."""
    session_gen = get_db()
    db = next(session_gen)
    summary: dict[str, str] = {}
    try:
        pairs = db.scalars(select(OhlcBar.pair).where(OhlcBar.timeframe == "1d").distinct()).all()
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=1)
        for pair in pairs:
            latest = db.scalar(select(func.max(OhlcBar.timestamp)).where(
                OhlcBar.pair == pair, OhlcBar.timeframe == "1d"))
            if latest is not None and latest.date() >= cutoff:
                summary[pair] = "fresh"
                continue
            try:
                result = sync_daily_pair(db, pair, outputsize=INCREMENTAL_BARS)
                summary[pair] = f"synced +{result['rows_inserted']} new bars"
                if result["rows_inserted"] > 0:
                    try:
                        predict(db, pair, persist=True)
                    except (LookupError, ValueError, RuntimeError):
                        pass  # no approved model yet for this pair
            except Exception as exc:  # keep going with the other pairs
                summary[pair] = f"failed: {exc}"
            time.sleep(PAUSE_BETWEEN_PAIRS)
    finally:
        session_gen.close()
    return summary


async def _loop() -> None:
    await asyncio.sleep(20)  # let the app finish starting; also acts as catch-up after downtime
    while True:
        try:
            summary = await asyncio.to_thread(run_update_once)
            log.info("Auto-update finished: %s", summary)
        except Exception:
            log.exception("Auto-update run failed")
        await asyncio.sleep(_seconds_until_next_run())


def start_auto_update() -> None:
    global _task
    if _enabled() and _task is None:
        _task = asyncio.create_task(_loop())
        log.info("Auto-update enabled: daily at %02d:00 UTC", _run_hour_utc())


async def stop_auto_update() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
