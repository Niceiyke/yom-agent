"""Message types for agent conversations with Pydantic validation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator


def _now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Message role enumeration."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """Base message type with Pydantic validation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    def to_dict(self) -> dict:
        return {
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Deserialize from dictionary."""
        role = MessageRole(data["role"])
        cls_map = {
            MessageRole.SYSTEM: SystemMessage,
            MessageRole.USER: UserMessage,
            MessageRole.ASSISTANT: AssistantMessage,
            MessageRole.TOOL: ToolMessage,
        }
        msg_cls = cls_map.get(role, Message)

        msg_kwargs = {
            "content": data["content"],
            "timestamp": datetime.fromisoformat(data.get("timestamp", _now().isoformat())),
            "metadata": data.get("metadata", {}),
        }

        if role == MessageRole.ASSISTANT:
            msg_kwargs["tool_calls"] = data.get("tool_calls", [])

        if role == MessageRole.TOOL:
            msg_kwargs["tool_name"] = data.get("tool_name", "")
            msg_kwargs["tool_call_id"] = data.get("tool_call_id")

        return msg_cls(**msg_kwargs)


class SystemMessage(Message):
    """System message (e.g., system prompt)."""
    role: MessageRole = Field(default=MessageRole.SYSTEM)


class UserMessage(Message):
    """User message."""
    role: MessageRole = Field(default=MessageRole.USER)


class AssistantMessage(Message):
    """Assistant message, may include tool calls."""
    role: MessageRole = Field(default=MessageRole.ASSISTANT)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ToolMessage(Message):
    """Tool result message."""
    role: MessageRole = Field(default=MessageRole.TOOL)
    tool_name: str = ""
    tool_call_id: str | None = None

    @field_validator("tool_call_id", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        if v == "":
            return None
        return v
