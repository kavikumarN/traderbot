"""Structured logging.

Two output formats are supported: ``json`` (production — one JSON object per
line, ready for a log aggregator) and ``console`` (local dev — short,
human-readable). A ``request_id`` contextvar lets every log line emitted
while handling a request carry that request's correlation id without
threading it through every function signature.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class RequestIdFilter(logging.Filter):
    """Injects the current request id (if any) into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_LOG_RECORD_ATTRS and key != "request_id"
        }
        if extras:
            payload["extra"] = extras
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None)
        prefix = f"[{request_id[:8]}] " if request_id else ""
        timestamp = self.formatTime(record, "%H:%M:%S")
        base = f"{timestamp} {record.levelname:<8} {record.name} — {prefix}{record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(settings: Settings) -> None:
    """Wire the root logger once, at process start.

    Idempotent: safe to call multiple times (e.g. once from ``main`` and
    again from a test fixture) because it always replaces the handler set
    rather than appending to it.
    """
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if settings.log_format == "json" else ConsoleFormatter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers unless we're actively debugging them.
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(
            logging.WARNING if not settings.debug else logging.INFO
        )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
