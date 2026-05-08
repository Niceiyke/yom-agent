"""Runtime response types with Pydantic validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TurnResult(BaseModel):
    """Result of a single agent turn."""
    assistant_message: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    turn_number: int = 0


class RuntimeRunResult(BaseModel):
    """Result of a complete runtime run."""
    session_id: str
    runtime_id: str
    final_message: str = ""
    turns: int = 0
    tool_calls_count: int = 0
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=_utcnow)

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
