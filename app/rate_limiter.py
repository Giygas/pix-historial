from datetime import datetime, timedelta
from typing import Callable, Dict, List

from fastapi import HTTPException, Request, Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.config import settings
from app.logger import logger


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm"""

    def __init__(self) -> None:
        self.requests: Dict[str, List[datetime]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed based on rate limit"""
        now = datetime.now()

        # Initialize if key doesn't exist
        if key not in self.requests:
            self.requests[key] = []

        # Remove old requests outside the window
        window_start = now - timedelta(seconds=settings.RATE_LIMIT_WINDOW)
        self.requests[key] = [
            req_time for req_time in self.requests[key] if req_time > window_start
        ]

        # Check if under limit
        if len(self.requests[key]) >= settings.RATE_LIMIT_REQUESTS:
            return False

        # Add current request
        self.requests[key].append(now)
        return True

    def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests for a key"""
        if key not in self.requests:
            return settings.RATE_LIMIT_REQUESTS

        now = datetime.now()
        window_start = now - timedelta(seconds=settings.RATE_LIMIT_WINDOW)

        # Count requests in current window
        recent_requests = [
            req_time for req_time in self.requests[key] if req_time > window_start
        ]

        return max(0, settings.RATE_LIMIT_REQUESTS - len(recent_requests))


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """Rate limiting middleware"""
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit
    if not rate_limiter.is_allowed(client_ip):
        remaining = rate_limiter.get_remaining_requests(client_ip)

        logger.warning(f"Rate limit exceeded for IP: {client_ip}")

        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RateLimitExceeded",
                "message": "Too many requests",
                "limit": settings.RATE_LIMIT_REQUESTS,
                "window": settings.RATE_LIMIT_WINDOW,
                "remaining": remaining,
                "retry_after": settings.RATE_LIMIT_WINDOW,
            },
        )

    # Process request
    response: Response = await call_next(request)

    # Add rate limit headers
    remaining = rate_limiter.get_remaining_requests(client_ip)
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Window"] = str(settings.RATE_LIMIT_WINDOW)

    return response
