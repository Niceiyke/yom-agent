"""Agent state model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from yom.models.messages import Message


def _now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class AgentState:
    """Mutable state for an agent session."""

    session_id: str
    runtime_id: str
    messages: list[Message] = field(default_factory=list)
    current_turn: int = 0
    max_turns: int = 50
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        runtime_id: str,
        session_id: str | None = None,
        initial_messages: list[Message] | None = None,
        max_turns: int = 50,
        system_prompt: str | None = None,
    ) -> AgentState:
        """Create a new agent state.

        Note: system_prompt is stored in metadata for LLM to use via system_prompt param,
        it is NOT added as a SystemMessage to avoid duplication with LLM's system parameter.
        """
        session_id = session_id or str(uuid.uuid4())
        messages = []
        if initial_messages:
            messages.extend(initial_messages)
        state = cls(
            session_id=session_id,
            runtime_id=runtime_id,
            messages=messages,
            max_turns=max_turns,
        )
        if system_prompt:
            state.metadata["system_prompt"] = system_prompt
        return state

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.updated_at = _now()

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        from yom.models.messages import UserMessage
        self.add_message(UserMessage(content=content))

    def add_assistant_message(self, content: str, tool_calls: list[dict] | None = None) -> None:
        """Add an assistant message."""
        from yom.models.messages import AssistantMessage
        msg = AssistantMessage(content=content, tool_calls=tool_calls)
        self.add_message(msg)

    def add_tool_message(
        self, tool_name: str, content: str, tool_call_id: str | None = None
    ) -> None:
        """Add a tool result message."""
        from yom.models.messages import ToolMessage
        msg = ToolMessage(
            tool_name=tool_name,
            content=content,
            tool_call_id=tool_call_id,
        )
        self.add_message(msg)

    def get_messages(self) -> list[Message]:
        """Get all messages."""
        return self.messages

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "runtime_id": self.runtime_id,
            "messages": [m.to_dict() for m in self.messages],
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentState:
        """Deserialize from dictionary."""
        from yom.models.messages import Message
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data["session_id"],
            runtime_id=data["runtime_id"],
            messages=messages,
            current_turn=data.get("current_turn", 0),
            max_turns=data.get("max_turns", 50),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )