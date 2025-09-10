from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "quotes"

    # External API
    QUOTES_API_URL: str = "https://your-api-endpoint.com/quotes"

    # Collection settings
    COLLECTION_INTERVAL: int = 300  # 5 minutes in seconds

    # API settings
    API_TITLE: str = "Pix price tracker"
    API_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"


settings = Settings()
