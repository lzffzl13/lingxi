import logging
import sys
from app.config import settings


def setup_logger(level: str = "INFO") -> logging.Logger:
    """Setup structured logger."""
    logger = logging.getLogger("lingxi")
    logger.setLevel(getattr(logging, level.upper()))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger(settings.LOG_LEVEL)
