from datetime import datetime, timezone

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from app.logger import logger
from app.exceptions import (
    QuoteAPIConnectionError,
    QuoteAPITimeoutError,
    QuoteDatabaseError,
    QuoteDataParsingError,
)

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

            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse API response: {e}")
                raise QuoteDataParsingError(
                    "Invalid JSON response", response.text[:100]
                )

            doc_id = await tracker.save_snapshot(data)
            logger.info(f"Successfully saved quotes with ID: {doc_id}")
            return doc_id

        except Timeout:
            logger.error(f"API request timed out after 30 seconds")
            raise QuoteAPITimeoutError("API request timed out", timeout=30)
        except ConnectionError as e:
            logger.error(f"Failed to connect to API: {e}")
            raise QuoteAPIConnectionError(
                "Failed to connect to API", url=settings.QUOTES_API_URL
            )
        except RequestException as e:
            logger.error(f"API request failed: {e}")
            raise QuoteAPIConnectionError(
                f"API request failed: {str(e)}", url=settings.QUOTES_API_URL
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


async def collect_quotes_background():
    """Background task to collect quotes periodically"""
    try:
        await QuoteService.fetch_and_save_quotes()
        logger.info(f"Background collection completed at {datetime.now(timezone.utc)}")

    except QuoteAPITimeoutError:
        logger.warning("Background collection timed out - will retry next interval")
    except QuoteAPIConnectionError:
        logger.warning(
            "Background collection failed to connect - will retry next interval"
        )
    except QuoteDataParsingError:
        logger.warning(
            "Background collection failed to parse data - will retry next interval"
        )
    except Exception as e:
        logger.error(f"Background collection failed: {e}")
