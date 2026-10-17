from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./forex.db"
    model_artifact_dir: str = "./models"
    default_pair: str = "EUR/USD"
    default_timeframe: str = "1d"
    admin_api_key: str = ""
    auto_prepare_pairs: bool = True
    # Twelve Data expects a bar count, not a yfinance-style period such as "5y".
    auto_prepare_outputsize: int = Field(1500, ge=260, le=5000)
    auto_prepare_stale_days: int = 4
    forecast_horizon_days: int = 30
    twelve_data_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        extra="ignore",
    )


settings = Settings()
