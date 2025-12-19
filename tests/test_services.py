from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from app.exceptions import QuoteAPIConnectionError
from app.services import QuoteService, collect_quotes_background


class TestQuoteService:
    """Test QuoteService class"""

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_success(self, mock_requests):
        """Test successful quote fetching and saving with USD support"""
        with patch("app.services.tracker") as mock_tracker:
            with patch("app.services.settings") as mock_settings:
                mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
                mock_tracker.save_snapshot = AsyncMock(
                    return_value="Saved: brlars=2 apps, usd=1 apps"
                )

                result = await QuoteService.fetch_and_save_quotes()

                assert result == "Saved: brlars=2 apps, usd=1 apps"
                mock_tracker.save_snapshot.assert_called_once()

                # Verify the API was called with correct parameters
                mock_requests.get.assert_called_with(
                    "https://test-api.com/quotes", timeout=30
                )

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_request_exception(self, mock_requests):
        """Test handling of request exceptions"""
        with patch("app.services.settings") as mock_settings:
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.RequestException(
                "Connection error"
            )

        from app.exceptions import QuoteAPIConnectionError

        with pytest.raises(QuoteAPIConnectionError, match="API request failed"):
            await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_timeout(self, mock_requests):
        """Test handling of timeout exceptions"""
        with patch("app.services.settings") as mock_settings:
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.Timeout("Request timed out")

        from app.exceptions import QuoteAPITimeoutError

        with pytest.raises(QuoteAPITimeoutError, match="API request timed out"):
            await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_http_error(self, mock_requests):
        """Test handling of HTTP errors"""
        with patch("app.services.settings") as mock_settings:
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "404 Not Found"
            )
            mock_requests.get.return_value = mock_response

        from app.exceptions import QuoteAPIConnectionError

        with pytest.raises(QuoteAPIConnectionError, match="API request failed"):
            await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_json_error(self, mock_requests):
        """Test handling of JSON parsing errors"""
        with patch("app.services.settings") as mock_settings:
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.text = "Invalid response text"
            mock_requests.get.return_value = mock_response

        from app.exceptions import QuoteDataParsingError

        with pytest.raises(QuoteDataParsingError, match="Invalid JSON response"):
            await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_database_error(self, mock_requests):
        """Test handling of database errors"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"test": "data"}
        mock_requests.get.return_value = mock_response

        with patch("app.services.tracker") as mock_tracker:
            mock_tracker.save_snapshot = AsyncMock(
                side_effect=Exception("Database error")
            )

            with pytest.raises(Exception, match="Database error"):
                await QuoteService.fetch_and_save_quotes()


class TestCollectQuotesBackground:
    """Test background quote collection function"""

    @pytest.mark.asyncio
    async def test_collect_quotes_background_success(self):
        """Test successful background collection"""
        with patch("app.services.QuoteService.fetch_and_save_quotes") as mock_fetch:
            mock_fetch.return_value = "507f1f77bcf86cd799439011"

            # Should not raise any exception
            await collect_quotes_background()

            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_quotes_background_failure(self):
        """Test background collection failure handling"""
        with patch("app.services.QuoteService.fetch_and_save_quotes") as mock_fetch:
            mock_fetch.side_effect = Exception("Collection failed")

            # Should raise exception to trigger retry mechanism
            with pytest.raises(Exception, match="Collection failed"):
                await collect_quotes_background()

            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_quotes_background_request_exception(self):
        """Test background collection with request exception"""
        with patch("app.services.QuoteService.fetch_and_save_quotes") as mock_fetch:
            mock_fetch.side_effect = requests.RequestException("API unavailable")

            # Should raise exception to trigger retry mechanism
            with pytest.raises(requests.RequestException, match="API unavailable"):
                await collect_quotes_background()

            mock_fetch.assert_called_once()


class TestQuoteServiceIntegration:
    """Integration tests for QuoteService"""

    @pytest.mark.asyncio
    async def test_full_integration_success(self, mock_requests):
        """Test full integration with mocked external dependencies"""
        # Setup mock response
        mock_response_data = {
            "app1": {
                "quotes": [{"symbol": "BRLARS", "buy": 1850.5}],
                "logo": "https://example.com/logo.png",
                "url": "https://app1.com",
                "isPix": True,
            }
        }

        mock_requests.get.return_value.json.return_value = mock_response_data
        mock_requests.get.return_value.raise_for_status = Mock()

        with patch("app.services.tracker") as mock_tracker:
            mock_tracker.save_snapshot = AsyncMock(return_value="test_doc_id")

            doc_id = await QuoteService.fetch_and_save_quotes()

            assert doc_id == "test_doc_id"
            mock_tracker.save_snapshot.assert_called_once_with(mock_response_data)

    @pytest.mark.asyncio
    async def test_error_propagation(self, mock_requests):
        """Test that errors are properly propagated"""
        with patch("app.services.settings") as mock_settings:
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.ConnectionError("Network error")

            with pytest.raises(QuoteAPIConnectionError):
                await QuoteService.fetch_and_save_quotes()
