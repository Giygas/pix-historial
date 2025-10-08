from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = Field(...)
    QUOTES_API_URL: str = Field(...)
    COLLECTION_CRON: str = (
        "*/15"  # Cron expression for scheduling (e.g., "*/15" for every 15 minutes)
    )
    MAX_HOURS: int = Field(default=720)
    API_TITLE: str = "PIX Historial API"
    API_VERSION: str = "1.0.0"


settings = Settings()  # type: ignore[call-arg]
