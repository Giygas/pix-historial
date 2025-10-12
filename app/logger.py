import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger() -> logging.Logger:
    """Setup logger with environment-aware configuration"""
    # Check if we're in test mode
    is_test_mode = (
        os.getenv("PYTEST_CURRENT_TEST") is not None or "pytest" in sys.modules
    )

    if is_test_mode:
        # In test mode, use a minimal logger that doesn't write to files
        logger = logging.getLogger("app")
        logger.setLevel(logging.WARNING)  # Only show warnings and errors in tests

        # Console handler for tests only
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    # Production/development logging setup
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Custom formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )

    # File handler for all logs
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Error file handler (errors only)
    error_handler = RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Configure application logger (not root logger)
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger


# Initialize logger
logger = setup_logger()
