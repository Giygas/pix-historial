import pytest
from unittest.mock import Mock, AsyncMock, patch
import requests

from app.services import QuoteService, collect_quotes_background


class TestQuoteServiceSimple:
    """Simplified QuoteService tests"""

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_success(self):
        """Test successful quote fetching and saving"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.tracker") as mock_tracker,
        ):
            # Setup mocks
            mock_response = Mock()
            mock_response.json.return_value = {"test": "data"}
            mock_response.raise_for_status = Mock()
            mock_requests.get.return_value = mock_response

            mock_tracker.save_snapshot = AsyncMock(
                return_value="507f1f77bcf86cd799439011"
            )

            doc_id = await QuoteService.fetch_and_save_quotes()

            assert doc_id == "507f1f77bcf86cd799439011"
            mock_requests.get.assert_called_once()
            mock_tracker.save_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_request_exception(self):
        """Test handling of request exceptions"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.settings") as mock_settings,
        ):
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.exceptions.RequestException(
                "Connection error"
            )

            from app.exceptions import QuoteAPIConnectionError

            with pytest.raises(QuoteAPIConnectionError, match="API request failed"):
                await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_timeout(self):
        """Test handling of timeout exceptions"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.settings") as mock_settings,
        ):
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.exceptions.Timeout(
                "Request timed out"
            )

            from app.exceptions import QuoteAPITimeoutError

            with pytest.raises(QuoteAPITimeoutError, match="API request timed out"):
                await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_http_error(self):
        """Test handling of HTTP errors"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.settings") as mock_settings,
        ):
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "404 Not Found"
            )
            mock_requests.get.return_value = mock_response

            from app.exceptions import QuoteAPIConnectionError

            with pytest.raises(QuoteAPIConnectionError, match="API request failed"):
                await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_json_error(self):
        """Test handling of JSON parsing errors"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.settings") as mock_settings,
        ):
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.text = "Invalid response text"
            mock_requests.get.return_value = mock_response

            from app.exceptions import QuoteDataParsingError

            with pytest.raises(QuoteDataParsingError, match="Invalid JSON response"):
                await QuoteService.fetch_and_save_quotes()

    @pytest.mark.asyncio
    async def test_fetch_and_save_quotes_database_error(self):
        """Test handling of database errors"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.tracker") as mock_tracker,
        ):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {"test": "data"}
            mock_requests.get.return_value = mock_response

            mock_tracker.save_snapshot = AsyncMock(
                side_effect=Exception("Database error")
            )

            with pytest.raises(Exception, match="Database error"):
                await QuoteService.fetch_and_save_quotes()


class TestCollectQuotesBackgroundSimple:
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
            mock_fetch.side_effect = requests.exceptions.RequestException(
                "API unavailable"
            )

            # Should raise exception to trigger retry mechanism
            with pytest.raises(
                requests.exceptions.RequestException, match="API unavailable"
            ):
                await collect_quotes_background()

            mock_fetch.assert_called_once()


class TestQuoteServiceIntegrationSimple:
    """Integration tests for QuoteService"""

    @pytest.mark.asyncio
    async def test_full_integration_success(self):
        """Test full integration with mocked external dependencies"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.tracker") as mock_tracker,
        ):
            # Setup mock response
            mock_response_data = {
                "app1": {
                    "quotes": [{"symbol": "BRLARS", "buy": 1850.5}],
                    "logo": "https://example.com/logo.png",
                    "url": "https://app1.com",
                    "isPix": True,
                }
            }

            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_requests.get.return_value = mock_response

            mock_tracker.save_snapshot = AsyncMock(return_value="test_doc_id")

            doc_id = await QuoteService.fetch_and_save_quotes()

            assert doc_id == "test_doc_id"
            mock_tracker.save_snapshot.assert_called_once_with(mock_response_data)

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that errors are properly propagated"""
        with (
            patch("app.services.requests") as mock_requests,
            patch("app.services.settings") as mock_settings,
        ):
            mock_settings.QUOTES_API_URL = "https://test-api.com/quotes"
            mock_requests.get.side_effect = requests.exceptions.ConnectionError(
                "Network error"
            )

            from app.exceptions import QuoteAPIConnectionError

            with pytest.raises(QuoteAPIConnectionError):
                await QuoteService.fetch_and_save_quotes()
