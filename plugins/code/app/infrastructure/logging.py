"""Structured logging setup."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """Outputs log records as JSON lines for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", json_output: bool = False) -> logging.Logger:
    """Configure and return the application root logger."""
    logger = logging.getLogger("code-intel")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stderr)

    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    logger.addHandler(handler)
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """Get a child logger under the code-intel namespace."""
    base = "code-intel"
    full_name = f"{base}.{name}" if name else base
    return logging.getLogger(full_name)
