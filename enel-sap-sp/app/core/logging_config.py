"""Logging configuration with request-id support."""
from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.settings import Settings


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Injects request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def set_request_id(value: str) -> Token:
    """Sets request id in context."""
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    """Resets request id context."""
    _request_id.reset(token)


def get_request_id() -> str:
    """Returns current request id."""
    return _request_id.get()


def configure_logging(settings: Settings) -> None:
    """Configures root logger only once."""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_sap_logging_configured", False):
        return

    level = getattr(logging, settings.log_level, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    request_filter = RequestIdFilter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(request_filter)
    root_logger.addHandler(stream_handler)

    log_path = settings.log_file
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_filter)
    root_logger.addHandler(file_handler)

    root_logger._sap_logging_configured = True
