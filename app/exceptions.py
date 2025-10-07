"""Custom exception classes for the quote service application."""

from typing import Any, Dict, Optional


class QuoteServiceError(Exception):
    """Base exception for quote service operations."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class QuoteAPIConnectionError(QuoteServiceError):
    """Failed to connect to external API."""

    def __init__(
        self, message: str = "Failed to connect to API", url: Optional[str] = None
    ):
        details = {"url": url} if url else {}
        super().__init__(message, details)


class QuoteAPITimeoutError(QuoteServiceError):
    """API request timed out."""

    def __init__(
        self, message: str = "API request timed out", timeout: Optional[int] = None
    ):
        details = {"timeout_seconds": timeout} if timeout else {}
        super().__init__(message, details)


class QuoteDatabaseError(QuoteServiceError):
    """Database operation failed."""

    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
    ):
        details = {"operation": operation} if operation else {}
        super().__init__(message, details)


class QuoteDataValidationError(QuoteServiceError):
    """Data validation failed."""

    def __init__(
        self, message: str = "Data validation failed", field: Optional[str] = None
    ):
        details = {"field": field} if field else {}
        super().__init__(message, details)


class QuoteDataParsingError(QuoteServiceError):
    """Failed to parse API response data."""

    def __init__(
        self,
        message: str = "Failed to parse API response",
        response_data: Optional[str] = None,
    ):
        details = {
            "response_preview": str(response_data)[:100] if response_data else None
        }
        super().__init__(message, details)
