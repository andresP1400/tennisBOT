"""Centralized logging configuration.

Replace `print(...)` calls scattered across the codebase with structured
JSON logging so logs can be aggregated, filtered, and shipped to a
centralized log stack.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for ingestion by log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            ):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False)


_configured = False


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Initialize root logger with JSON or plain handler."""
    global _configured
    if _configured:
        return
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream=sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, initializing logging on first call."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
