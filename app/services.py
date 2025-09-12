from datetime import datetime, timezone

import requests

from app.logger import logger

from .config import settings
from .database import tracker


class QuoteService:
    """Service layer for quote-related operations"""

    @staticmethod
    async def fetch_and_save_quotes() -> str:
        """Fetch quotes from external API and save to database"""
        try:
            response = requests.get(settings.QUOTES_API_URL, timeout=30)
            response.raise_for_status()

            doc_id = await tracker.save_snapshot(response.json())
            logger.info(f"Successfully saved quotes with ID: {doc_id}")
            return doc_id

        except requests.RequestException as e:
            logger.error(f"Failed to fetch quotes from API: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to save quotes: {e}")
            raise


async def collect_quotes_background():
    """Background task to collect quotes periodically"""
    try:
        await QuoteService.fetch_and_save_quotes()
        logger.info(f"Background collection completed at {datetime.now(timezone.utc)}")

    except Exception as e:
        logger.error(f"Background collection failed: {e}")
