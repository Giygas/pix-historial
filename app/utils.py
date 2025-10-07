"""Utility functions for the quote service application."""

import asyncio
import time
from functools import wraps
from typing import Callable, Optional, Tuple, Type, Any, Union

from app.logger import logger


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    backoff_factor: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exceptions: Tuple of exception types to retry on
        backoff_factor: Multiplier for exponential backoff
        jitter: Whether to add random jitter to delay
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Final error: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        import random

                        delay *= 0.5 + random.random() * 0.5

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}. "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("Unexpected error in retry mechanism")

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Final error: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        import random

                        delay *= 0.5 + random.random() * 0.5

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}. "
                        f"Retrying in {delay:.2f}s. Error: {e}"
                    )
                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("Unexpected error in retry mechanism")

        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RetryConfig:
    """Configuration class for retry settings."""

    # Network operations - more aggressive retry
    NETWORK_RETRY = {
        "max_attempts": 3,
        "base_delay": 1.0,
        "max_delay": 10.0,
        "backoff_factor": 2.0,
        "jitter": True,
    }

    # Database operations - conservative retry
    DATABASE_RETRY = {
        "max_attempts": 2,
        "base_delay": 0.5,
        "max_delay": 5.0,
        "backoff_factor": 2.0,
        "jitter": True,
    }

    # Background tasks - very conservative
    BACKGROUND_RETRY = {
        "max_attempts": 2,
        "base_delay": 2.0,
        "max_delay": 30.0,
        "backoff_factor": 2.0,
        "jitter": True,
    }
