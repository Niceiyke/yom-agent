"""Runtime response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TurnResult:
    """Result of a single agent turn."""
    assistant_message: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    turn_number: int = 0


@dataclass
class RuntimeRunResult:
    """Result of a complete runtime run."""
    session_id: str
    runtime_id: str
    final_message: str
    turns: int = 0
    tool_calls_count: int = 0
    error: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "final_message": self.final_message,
            "turns": self.turns,
            "tool_calls_count": self.tool_calls_count,
            "error": self.error,
            "usage": self.usage,
            "metadata": self.metadata,
            "completed_at": self.completed_at.isoformat(),
        }