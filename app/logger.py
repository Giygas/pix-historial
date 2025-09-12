import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

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

# Configure root logger
root_logger = logging.getLogger(__name__)
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(console_handler)

logger = root_logger
