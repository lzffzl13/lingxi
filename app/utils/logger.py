import json
import logging
import sys
from datetime import datetime

from app.config import settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields
        for key in ["session_id", "tool_name", "request_id", "user_id"]:
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        name = record.name
        message = record.getMessage()

        # Add context info if present
        context_parts = []
        for key in ["session_id", "tool_name"]:
            if hasattr(record, key):
                context_parts.append(f"{key}={getattr(record, key)}")

        context = f" [{', '.join(context_parts)}]" if context_parts else ""
        return f"{timestamp} | {level:8s} | {name}{context} | {message}"


def setup_logger(level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Setup structured logger.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, use JSON format; otherwise use text format
    """
    logger = logging.getLogger("lingxi")
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on environment
    if json_format or settings.APP_ENV == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Determine format based on environment
_use_json = settings.APP_ENV == "production"
logger = setup_logger(settings.LOG_LEVEL, json_format=_use_json)


def get_logger_with_context(**kwargs) -> logging.LoggerAdapter:
    """Get a logger with additional context fields.

    Example:
        log = get_logger_with_context(session_id="abc123")
        log.info("Processing message")  # Will include session_id in output
    """
    return logging.LoggerAdapter(logger, kwargs)
