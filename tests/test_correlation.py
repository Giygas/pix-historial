"""Tests for correlation ID functionality."""

import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request, Response

from app.config import settings
from app.correlation import CorrelationIDMiddleware, get_correlation_id


class TestCorrelationIDMiddleware:
    """Test cases for CorrelationIDMiddleware."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.url.query = ""
        request.headers = Mock()
        request.headers.get = Mock(return_value=None)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function."""
        response = Mock(spec=Response)
        response.status_code = 200
        response.headers = {}
        return AsyncMock(return_value=response)

    @pytest.fixture
    def correlation_middleware(self):
        """Create correlation middleware instance."""
        return CorrelationIDMiddleware(Mock())

    @pytest.mark.asyncio
    async def test_generates_new_correlation_id_when_none_provided(
        self, correlation_middleware, mock_request, mock_call_next
    ):
        """Test that middleware generates new correlation ID when none provided."""
        # Ensure no X-Request-ID header
        mock_request.headers.get.return_value = None

        # Call middleware
        response = await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify correlation ID was generated and stored
        assert hasattr(mock_request.state, "correlation_id")
        assert uuid.UUID(mock_request.state.correlation_id)  # Valid UUID format

        # Verify correlation ID was added to response headers
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] == mock_request.state.correlation_id

        # Verify call_next was called
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_uses_existing_correlation_id_when_provided(
        self, correlation_middleware, mock_request, mock_call_next
    ):
        """Test that middleware uses existing correlation ID when provided."""
        # Set existing correlation ID
        existing_id = str(uuid.uuid4())
        mock_request.headers.get.return_value = existing_id

        # Call middleware
        response = await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify existing correlation ID was used
        assert mock_request.state.correlation_id == existing_id
        assert response.headers["X-Request-ID"] == existing_id

    @pytest.mark.asyncio
    async def test_skips_correlation_when_disabled(
        self, correlation_middleware, mock_request, mock_call_next, monkeypatch
    ):
        """Test that middleware skips correlation processing when disabled."""
        # Disable correlation IDs
        monkeypatch.setattr(settings, "ENABLE_CORRELATION_IDS", False)

        # Reset mock state to not have correlation_id
        del mock_request.state.correlation_id

        # Call middleware
        response = await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify no correlation ID processing
        assert not hasattr(mock_request.state, "correlation_id")
        assert "X-Request-ID" not in response.headers

    @pytest.mark.asyncio
    async def test_logs_request_start_and_completion(
        self, correlation_middleware, mock_request, mock_call_next, caplog
    ):
        """Test that middleware logs request start and completion."""
        # Set up correlation ID
        correlation_id = str(uuid.uuid4())
        mock_request.headers.get.return_value = correlation_id

        # Enable logging capture for our logger
        with caplog.at_level("INFO", logger="app"):
            # Call middleware
            await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify logs contain correlation ID
        log_messages = [record.message for record in caplog.records]
        assert any(
            f"[{correlation_id}] Request started:" in msg for msg in log_messages
        )
        assert any(
            f"[{correlation_id}] Request completed:" in msg for msg in log_messages
        )

    @pytest.mark.asyncio
    async def test_logs_exceptions_with_correlation_id(
        self, correlation_middleware, mock_request, caplog
    ):
        """Test that middleware logs exceptions with correlation ID."""
        # Set up correlation ID and exception
        correlation_id = str(uuid.uuid4())
        mock_request.headers.get.return_value = correlation_id

        mock_call_next = AsyncMock(side_effect=Exception("Test error"))

        # Call middleware and expect exception
        with pytest.raises(Exception, match="Test error"):
            await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify exception log contains correlation ID
        log_messages = [record.message for record in caplog.records]
        assert any(
            f"[{correlation_id}] Request failed with exception:" in msg
            for msg in log_messages
        )

    @pytest.mark.asyncio
    async def test_preserves_response_headers(
        self, correlation_middleware, mock_request, mock_call_next
    ):
        """Test that middleware preserves existing response headers."""
        # Set up response with existing headers
        existing_response = Mock(spec=Response)
        existing_response.status_code = 200
        existing_response.headers = {"Existing-Header": "existing-value"}
        mock_call_next.return_value = existing_response

        # Call middleware
        response = await correlation_middleware.dispatch(mock_request, mock_call_next)

        # Verify existing headers are preserved
        assert response.headers["Existing-Header"] == "existing-value"
        assert "X-Request-ID" in response.headers


class TestGetCorrelationID:
    """Test cases for get_correlation_id helper function."""

    def test_get_correlation_id_from_request_state(self):
        """Test getting correlation ID from request state."""
        request = Mock(spec=Request)
        request.state.correlation_id = "test-correlation-id"

        result = get_correlation_id(request)
        assert result == "test-correlation-id"

    def test_get_correlation_id_when_missing(self):
        """Test getting correlation ID when not present."""
        request = Mock(spec=Request)
        # Don't set correlation_id on state
        del request.state.correlation_id

        result = get_correlation_id(request)
        assert result == "unknown"

    def test_get_correlation_id_when_state_missing(self):
        """Test getting correlation ID when state is missing."""
        request = Mock(spec=Request)
        # Remove state attribute completely
        del request.state

        result = get_correlation_id(request)
        assert result == "unknown"
