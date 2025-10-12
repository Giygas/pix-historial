from datetime import datetime, timezone

import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from app.logger import logger
from app.exceptions import (
    QuoteAPIConnectionError,
    QuoteAPITimeoutError,
    QuoteDataParsingError,
)
from app.utils import retry_with_backoff, RetryConfig

from .config import settings
from .database import tracker


class QuoteService:
    """Service layer for quote-related operations"""

    @staticmethod
    @retry_with_backoff(
        exceptions=(Timeout, ConnectionError, RequestException),
        **RetryConfig.NETWORK_RETRY,
    )
    def _fetch_from_api() -> requests.Response:
        """Internal method to fetch data from API with retry logic."""
        response = requests.get(settings.QUOTES_API_URL, timeout=30)
        response.raise_for_status()
        return response

    @staticmethod
    @retry_with_backoff(exceptions=(Exception,), **RetryConfig.DATABASE_RETRY)
    async def _save_to_database(data: dict) -> str:
        """Internal method to save data to database with retry logic."""
        return await tracker.save_snapshot(data)

    @staticmethod
    async def fetch_and_save_quotes() -> str:
        """Fetch quotes from external API and save to database"""
        try:
            # Fetch data from API with retry
            response = QuoteService._fetch_from_api()

            # Parse JSON response
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse API response: {e}")
                raise QuoteDataParsingError(
                    "Invalid JSON response", response.text[:100]
                )

            # Save to database with retry
            doc_id = await QuoteService._save_to_database(data)
            logger.info(f"Successfully saved quotes with ID: {doc_id}")
            return doc_id

        except Timeout:
            logger.error("API request timed out after 30 seconds")
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


@retry_with_backoff(
    exceptions=(QuoteAPITimeoutError, QuoteAPIConnectionError, QuoteDataParsingError),
    **RetryConfig.BACKGROUND_RETRY,
)
async def collect_quotes_background():
    """Background task to collect quotes periodically"""
    try:
        await QuoteService.fetch_and_save_quotes()
        logger.info(f"Background collection completed at {datetime.now(timezone.utc)}")

    except QuoteAPITimeoutError:
        logger.warning("Background collection timed out - will retry next interval")
        raise  # Re-raise to trigger retry mechanism
    except QuoteAPIConnectionError:
        logger.warning(
            "Background collection failed to connect - will retry next interval"
        )
        raise  # Re-raise to trigger retry mechanism
    except QuoteDataParsingError:
        logger.warning(
            "Background collection failed to parse data - will retry next interval"
        )
        raise  # Re-raise to trigger retry mechanism
    except Exception as e:
        logger.error(f"Background collection failed: {e}")
        raise  # Re-raise to trigger retry mechanism
