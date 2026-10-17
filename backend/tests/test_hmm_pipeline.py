"""Offline regression coverage for search preparation and the fitted HMM."""

import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api import search
from app.core.config import settings
from app.db.models import Base, DataSyncRun, HmmModel, OhlcBar
from app.schemas import SearchResponse
from app.services.market_data import sync_daily_pair


def sample_bars() -> list[dict]:
    today = datetime.now(timezone.utc).date()
    days_since_friday = (today.weekday() - 4) % 7 or 7
    last_friday = today - timedelta(days=days_since_friday)
    dates = pd.bdate_range(end=last_friday, periods=320)
    rng = np.random.default_rng(42)
    price = 1.10
    bars = []
    for index, day in enumerate(dates):
        regime = index // 110
        daily_return = (-0.001, 0.0, 0.001)[regime] + rng.normal(0, 0.0005)
        opening = price
        price = opening * math.exp(daily_return)
        bars.append({
            "datetime": day.strftime("%Y-%m-%d"),
            "open": str(opening),
            "high": str(max(opening, price) * 1.001),
            "low": str(min(opening, price) * 0.999),
            "close": str(price),
        })
    bars.append({"datetime": "2000-01-01", "open": "0", "high": "1", "low": "0", "close": "0"})
    bars.append(dict(bars[100]))  # a provider duplicate must not violate the OHLC unique key
    return bars


class HmmPipelineTest(unittest.TestCase):
    def test_search_prepares_and_reuses_an_approved_hmm(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        workspace_tmp = Path(__file__).resolve().parents[2] / ".tmp"
        workspace_tmp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=workspace_tmp) as artifacts, Session(engine, expire_on_commit=False) as db:
            with patch("app.services.market_data.fetch_daily_bars", return_value=sample_bars()) as fetch, \
                 patch.object(settings, "model_artifact_dir", artifacts), \
                 patch.object(settings, "auto_prepare_pairs", True), \
                 patch.object(settings, "auto_prepare_stale_days", 14), \
                 patch.object(settings, "auto_prepare_outputsize", 320):
                first = search("EURUSD", "1d", 250, 30, db)
                SearchResponse.model_validate(first, from_attributes=True)
                self.assertEqual(first["prepared_steps"], ["synced", "trained"])
                fetch.assert_called_once_with("EUR/USD", 320)
                self.assertEqual(db.scalar(select(func.count(OhlcBar.id))), 320)

                model = db.scalar(select(HmmModel).where(HmmModel.status == "approved"))
                self.assertIsNotNone(model)
                self.assertTrue(model.metrics_json["auto_approved"])
                self.assertTrue(math.isfinite(model.metrics_json["validation_log_likelihood"]))
                self.assertTrue(Path(model.artifact_uri).is_file())

                prediction = first["prediction"]
                forecast = first["forecast"]
                self.assertEqual(prediction["model_version"], forecast["model_version"])
                self.assertAlmostEqual(sum(prediction["current_probabilities"].values()), 1.0)
                self.assertAlmostEqual(sum(prediction["next_state_probabilities"].values()), 1.0)
                self.assertEqual(prediction["forecast_for_timestamp"].date(), forecast["points"][0]["timestamp"].date())
                self.assertEqual(prediction["forecast_for_timestamp"].weekday(), 0)
                self.assertEqual(len(forecast["points"]), 30)
                for point in forecast["points"]:
                    self.assertLessEqual(point["lower"], point["expected"])
                    self.assertLessEqual(point["expected"], point["upper"])
                    self.assertGreater(point["lower"], 0)

                second = search("EURUSD", "1d", 250, 30, db)
                self.assertEqual(second["prepared_steps"], [])
                fetch.assert_called_once()

                repeated_sync = sync_daily_pair(db, "EUR/USD", outputsize=320)
                self.assertEqual(repeated_sync["rows_inserted"], 0)
                self.assertEqual(repeated_sync["rows_updated"], 320)
                self.assertEqual(db.scalar(select(func.count(OhlcBar.id))), 320)

                # A five-minute dashboard refresh must not repeatedly spend API
                # credits when the last stored daily bar is old.
                with patch.object(settings, "auto_prepare_stale_days", 0):
                    recent = search("EURUSD", "1d", 250, 30, db)
                    self.assertEqual(recent["prepared_steps"], [])
                    self.assertEqual(fetch.call_count, 2)

                    for run in db.scalars(select(DataSyncRun)).all():
                        run.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
                    db.commit()
                    due = search("EURUSD", "1d", 250, 30, db)
                    self.assertEqual(due["prepared_steps"], ["synced"])
                    fetch.assert_called_with("EUR/USD", 30)
                    self.assertEqual(db.scalar(select(func.count(OhlcBar.id))), 320)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
