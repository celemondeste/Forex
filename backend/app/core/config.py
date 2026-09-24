from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./forex.db"
    model_artifact_dir: str = "./models"
    default_pair: str = "EUR/USD"
    default_timeframe: str = "1d"
    admin_api_key: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")


settings = Settings()
