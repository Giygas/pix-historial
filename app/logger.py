import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    handlers=[
        # Main app logs
        RotatingFileHandler("logs/app.log", maxBytes=50 * 1024 * 1024, backupCount=10),
        # Error-only logs
        RotatingFileHandler(
            "logs/errors.log", maxBytes=10 * 1024 * 1024, backupCount=5
        ),
        # Console output
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)
