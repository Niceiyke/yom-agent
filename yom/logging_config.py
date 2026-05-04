"""Logging configuration for yom runtime."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yom.runtime.config import RuntimeSettings


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_LOG_LEVEL = "INFO"


def setup_logging(
    level: str = DEFAULT_LOG_LEVEL,
    format_string: str = LOG_FORMAT,
    date_format: str = DATE_FORMAT,
    handler: logging.Handler | None = None,
) -> None:
    """Configure logging for yom runtime."""
    if handler is None:
        handler = logging.StreamHandler(sys.stderr)

    formatter = logging.Formatter(format_string, datefmt=date_format)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("yom")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("yom.providers").setLevel(logging.WARNING)
    logging.getLogger("yom.loop").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"yom.{name}")


class LogContext:
    """Context manager for temporary log level changes."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.old_level: int | None = None

    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, *args):
        if self.old_level is not None:
            self.logger.setLevel(self.old_level)


def configure_from_settings(settings: "RuntimeSettings") -> None:
    """Configure logging from RuntimeSettings."""
    if settings.log_level:
        level = settings.log_level.upper()
        setup_logging(level=level)


class StructuredLogger:
    """Logger wrapper that supports structured logging with extra fields."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _format_message(self, msg: str, **kwargs) -> str:
        """Format message with extra fields."""
        if not kwargs:
            return msg
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{msg} [{extra}]"

    def debug(self, msg: str, **kwargs) -> None:
        self._logger.debug(self._format_message(msg, **kwargs))

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(self._format_message(msg, **kwargs))

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(self._format_message(msg, **kwargs))

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(self._format_message(msg, **kwargs))

    def exception(self, msg: str, **kwargs) -> None:
        self._logger.exception(self._format_message(msg, **kwargs))


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    return StructuredLogger(get_logger(name))