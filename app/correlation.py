"""Request correlation ID middleware for better debugging and monitoring."""

import uuid
from typing import Callable, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logger import logger


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs to all requests for better tracing.

    This middleware:
    1. Extracts existing correlation ID from X-Request-ID header
    2. Generates new UUID if none provided
    3. Stores correlation ID in request.state for easy access
    4. Adds correlation ID to response headers
    5. Adds correlation ID to logging context
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip correlation ID processing if disabled
        if not settings.ENABLE_CORRELATION_IDS:
            return await call_next(request)

        # Extract existing correlation ID or generate new one
        correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in request state for easy access throughout the application
        request.state.correlation_id = correlation_id

        # Log the start of the request with correlation ID
        logger.info(
            f"[{correlation_id}] Request started: {request.method} {request.url.path}",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        # Process the request
        try:
            response: Response = await call_next(request)
        except Exception as e:
            # Log the error with correlation ID before re-raising
            logger.error(
                f"[{correlation_id}] Request failed with exception: {str(e)}",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "exception_type": type(e).__name__,
                    "exception_message": str(e),
                },
            )
            raise

        # Add correlation ID to response headers for client tracking
        response.headers["X-Request-ID"] = correlation_id

        # Log the completion of the request
        logger.info(
            f"[{correlation_id}] Request completed: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "response_time": getattr(response, "elapsed_time", None),
            },
        )

        return response


def get_correlation_id(request: Request) -> str:
    """
    Helper function to get correlation ID from request.

    Args:
        request: FastAPI request object

    Returns:
        Correlation ID string or "unknown" if not available
    """
    try:
        return getattr(request.state, "correlation_id", "unknown")
    except AttributeError:
        return "unknown"
