"""Live price for the chart's last candle, with a short server-side cache.

Save as backend/app/services/live.py
"""
import threading
import time
from datetime import datetime, timezone

import requests

from app.core.config import settings

PRICE_URL = "https://api.twelvedata.com/price"
CACHE_SECONDS = 60  # free plan has a daily credit budget; one upstream call per pair per minute

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def get_live_price(pair: str) -> dict:
    now = time.time()
    with _lock:
        hit = _cache.get(pair)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]

    if not settings.twelve_data_api_key:
        raise ValueError("TWELVE_DATA_API_KEY is not configured")
    response = requests.get(PRICE_URL, params={"symbol": pair, "apikey": settings.twelve_data_api_key}, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("status") == "error" or "price" not in data:
        raise ValueError(f"Twelve Data error {data.get('code')}: {data.get('message')}")

    payload = {
        "pair": pair,
        "price": float(data["price"]),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "refresh_seconds": CACHE_SECONDS,
    }
    with _lock:
        _cache[pair] = (now, payload)
    return payload
