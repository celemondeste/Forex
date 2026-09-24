import numpy as np
import pandas as pd

FEATURE_VERSION = "fx-daily-v1"
FEATURE_COLUMNS = ["log_return", "intrabar_return", "daily_range", "volatility_20"]


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build causal daily features; rows without a full volatility window are omitted."""
    result = pd.DataFrame(index=frame.index)
    close = frame["close"].astype(float)
    result["log_return"] = np.log(close).diff()
    result["intrabar_return"] = np.log(frame["close"] / frame["open"])
    result["daily_range"] = (frame["high"] - frame["low"]) / close
    result["volatility_20"] = result["log_return"].rolling(20, min_periods=20).std()
    return result.replace([np.inf, -np.inf], np.nan).dropna()
