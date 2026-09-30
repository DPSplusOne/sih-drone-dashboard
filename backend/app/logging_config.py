"""Small JSON logging setup shared by AeroTrace API modules."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


_STANDARD_RECORD_FIELDS = set(logging.LogRecord(None, None, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Serialize application logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> logging.Logger:
    """Configure and return the isolated AeroTrace application logger once."""

    logger = logging.getLogger("aerotrace")
    logger.setLevel(level)
    logger.propagate = False

    if not any(getattr(handler, "_aerotrace_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._aerotrace_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)

    return logger
