from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./forex.db"
    model_artifact_dir: str = "./models"
    default_pair: str = "EUR/USD"
    default_timeframe: str = "1d"
    admin_api_key: str = ""
    auto_prepare_pairs: bool = True
    auto_prepare_period: str = "5y"
    auto_prepare_stale_days: int = 4
    forecast_horizon_days: int = 30

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")


settings = Settings()
