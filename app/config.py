from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = Field(...)
    QUOTES_API_URL: str = Field(...)
    COLLECTION_CRON: str = (
        "*/15"  # Cron expression for scheduling (e.g., "*/15" for every 15 minutes)
    )
    API_TITLE: str = Field(...)
    API_VERSION: str = Field(...)

    class Config:
        env_file = ".env"


settings = Settings()  # type: ignore[call-arg]
