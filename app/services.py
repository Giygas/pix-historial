from datetime import datetime, timezone

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

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

        except Timeout:
            logger.error("API request timed out")
            raise
        except ConnectionError:
            logger.error("Failed to connect to API")
            raise
        except RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


async def collect_quotes_background():
    """Background task to collect quotes periodically"""
    try:
        await QuoteService.fetch_and_save_quotes()
        logger.info(f"Background collection completed at {datetime.now(timezone.utc)}")

    except Timeout:
        logger.warning("Background collection timed out - will retry next interval")
    except ConnectionError:
        logger.warning(
            "Background collection failed to connect - will retry next interval"
        )
    except Exception as e:
        logger.error(f"Background collection failed: {e}")
