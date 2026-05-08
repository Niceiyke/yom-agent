"""Debug mode and tracing for yom-agent.

Enable with:
    YOM_DEBUG=1 python my_agent.py

Or programmatically:
    from yom.debug import enable_debug
    enable_debug()
"""

from __future__ import annotations

import os
import time
import traceback
import logging


DEBUG = os.environ.get("YOM_DEBUG", "0") == "1"
TRACE = os.environ.get("YOM_TRACE", "0") == "1"


def enable_debug() -> None:
    """Enable debug mode."""
    global DEBUG
    DEBUG = True
    logging.getLogger("yom").setLevel(logging.DEBUG)


def enable_trace() -> None:
    """Enable full trace mode."""
    global DEBUG, TRACE
    DEBUG = True
    TRACE = True
    logging.getLogger("yom").setLevel(logging.DEBUG)


def disable_debug() -> None:
    """Disable debug mode."""
    global DEBUG, TRACE
    DEBUG = False
    TRACE = False


# =============================================================================
# Trace Context Manager
# =============================================================================

class TraceContext:
    """Context manager for tracing code blocks."""

    def __init__(self, name: str, **data):
        self.name = name
        self.data = data
        self.start_time: float = 0

    def __enter__(self):
        self.start_time = time.time()
        if DEBUG:
            print(f"[YOM] {self.name} started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start_time) * 1000
        if exc_val:
            print(f"[YOM] {self.name} failed after {duration:.1f}ms: {exc_val}")
            if TRACE:
                traceback.print_exception(exc_type, exc_val, exc_tb)
        elif DEBUG:
            print(f"[YOM] {self.name} completed in {duration:.1f}ms")


def trace(name: str, **data) -> TraceContext:
    """Create a trace context for timing code blocks."""
    return TraceContext(name, **data)


__all__ = [
    "DEBUG",
    "TRACE",
    "enable_debug",
    "enable_trace",
    "disable_debug",
    "TraceContext",
    "trace",
]
