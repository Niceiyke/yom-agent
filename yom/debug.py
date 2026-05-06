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
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from pathlib import Path


# =============================================================================
# Debug Configuration
# =============================================================================

DEBUG = os.environ.get("YOM_DEBUG", "0") == "1"
TRACE = os.environ.get("YOM_TRACE", "0") == "1"
VERBOSE = os.environ.get("YOM_VERBOSE", "0") == "1"


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
# Trace Events
# =============================================================================

@dataclass
class TraceEvent:
    """A trace event."""
    timestamp: float
    event_type: str
    data: dict[str, Any]
    duration_ms: float | None = None


class TraceRecorder:
    """Record trace events."""

    def __init__(self, max_events: int = 10000):
        self.events: list[TraceEvent] = []
        self.max_events = max_events
        self._enabled = TRACE

    def record(
        self,
        event_type: str,
        data: dict[str, Any],
        duration_ms: float | None = None,
    ) -> None:
        """Record a trace event."""
        if not self._enabled:
            return

        event = TraceEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data,
            duration_ms=duration_ms,
        )
        self.events.append(event)

        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

    def get_trace(self) -> list[dict]:
        """Get trace as list of dicts."""
        return [
            {
                "timestamp": e.timestamp,
                "event": e.event_type,
                "duration_ms": e.duration_ms,
                **e.data,
            }
            for e in self.events
        ]

    def save_trace(self, path: str | Path) -> None:
        """Save trace to file."""
        with open(path, "w") as f:
            json.dump(self.get_trace(), f, indent=2, default=str)

    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()


# Global trace recorder
_trace_recorder = TraceRecorder()


def get_recorder() -> TraceRecorder:
    """Get the global trace recorder."""
    return _trace_recorder


# =============================================================================
# Context Manager for Tracing
# =============================================================================

class TraceContext:
    """Context manager for tracing code blocks."""

    def __init__(self, event_type: str, **data):
        self.event_type = event_type
        self.data = data
        self.start_time: float = 0

    def __enter__(self):
        self.start_time = time.time()
        _trace_recorder.record(self.event_type, {"enter": True, **self.data})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start_time) * 1000
        _trace_recorder.record(
            self.event_type,
            {
                "exit": True,
                "error": str(exc_val) if exc_val else None,
                **self.data,
            },
            duration_ms=duration,
        )
        if exc_val and DEBUG:
            print(f"[YOM DEBUG] {self.event_type} failed after {duration:.1f}ms")
            if VERBOSE:
                traceback.print_exception(exc_type, exc_val, exc_tb)


# =============================================================================
# Debug Utilities
# =============================================================================

class DebugWriter:
    """Write debug output to file or console."""

    def __init__(self, output_path: str | Path | None = None):
        self.output_path = Path(output_path) if output_path else None
        self.buffer: list[str] = []

    def write(self, *args, **kwargs) -> None:
        """"Write debug output."""
        msg = " ".join(str(a) for a in args)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        line = f"[{timestamp}] {msg}"
        self.buffer.append(line)

        if DEBUG:
            print(line, **kwargs)

        if self.output_path:
            with open(self.output_path, "a") as f:
                f.write(line + "\n")

    def flush(self) -> None:
        """Flush buffer."""
        self.buffer.clear()

    def get_buffer(self) -> list[str]:
        """Get current buffer."""
        return list(self.buffer)


# Global debug writer
_debug_writer = DebugWriter()


def debug(*args, **kwargs) -> None:
    """Write debug output."""
    if DEBUG:
        _debug_writer.write(*args, **kwargs)


def trace(event_type: str, **data) -> TraceContext:
    """Create a trace context."""
    return TraceContext(event_type, **data)


# =============================================================================
# State Inspector
# =============================================================================

def inspect_state(state: Any) -> dict[str, Any]:
    """Inspect agent state and return debug info."""
    info: dict[str, Any] = {
        "type": type(state).__name__,
    }

    if hasattr(state, "__dict__"):
        attrs: dict[str, Any] = {}
        for key, value in state.__dict__.items():
            if key.startswith("_"):
                continue
            if callable(value):
                attrs[key] = "<method>"
            elif hasattr(value, "__len__") and hasattr(value, "__iter__"):
                attrs[key] = f"<list len={len(value)}>"
            elif isinstance(value, dict):
                attrs[key] = f"<dict keys={list(value.keys())[:5]}>"
            else:
                try:
                    attrs[key] = str(value)[:100]
                except Exception:
                    attrs[key] = "<unprintable>"
        info["attrs"] = attrs

    return info


def format_trace_html(trace_data: list[dict] | None = None) -> str:
    """Format trace as HTML for visualization."""
    if trace_data is None:
        trace_data = _trace_recorder.get_trace()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>yom trace</title>
        <style>
            body { font-family: monospace; background: #1e1e1e; color: #ddd; padding: 20px; }
            .event { padding: 8px; margin: 4px 0; background: #2d2d2d; border-radius: 4px; }
            .turn { border-left: 3px solid #4ec9b0; }
            .tool { border-left: 3px solid #ce9178; }
            .error { border-left: 3px solid #f14c4c; }
            .time { color: #888; font-size: 0.9em; }
            .duration { color: #4ec9b0; }
        </style>
    </head>
    <body>
        <h1>yom trace</h1>
        <div id="trace">
    """

    for event in trace_data:
        event_type = event.get("event", "unknown")
        event_class = "event"
        if "turn" in event_type.lower():
            event_class += " turn"
        elif "tool" in event_type.lower():
            event_class += " tool"
        elif event.get("error"):
            event_class += " error"

        timestamp = datetime.fromtimestamp(event.get("timestamp", 0)).strftime("%H:%M:%S.%f")[:-3]
        duration = event.get("duration_ms")
        duration_str = f'<span class="duration">{duration:.1f}ms</span>' if duration else ""

        html += f"""
        <div class="{event_class}">
            <span class="time">{timestamp}</span>
            {event_type}
            {duration_str}
        </div>
        """

    html += """
        </div>
    </body>
    </html>
    """
    return html


__all__ = [
    "DEBUG",
    "TRACE",
    "VERBOSE",
    "enable_debug",
    "enable_trace",
    "disable_debug",
    "TraceRecorder",
    "TraceContext",
    "TraceEvent",
    "get_recorder",
    "trace",
    "DebugWriter",
    "debug",
    "inspect_state",
    "format_trace_html",
]
