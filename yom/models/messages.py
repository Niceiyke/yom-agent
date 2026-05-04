"""Message types for agent conversations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class MessageRole(str, Enum):
    """Message role enumeration."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Base message type."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        role = MessageRole(data["role"])
        cls_map = {
            MessageRole.SYSTEM: SystemMessage,
            MessageRole.USER: UserMessage,
            MessageRole.ASSISTANT: AssistantMessage,
            MessageRole.TOOL: ToolMessage,
        }
        msg_cls = cls_map.get(role, Message)
        return msg_cls(
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", _now().isoformat())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SystemMessage(Message):
    """System message (e.g., system prompt)."""
    role: MessageRole = field(default=MessageRole.SYSTEM, init=False)

    def __post_init__(self):
        self.role = MessageRole.SYSTEM


@dataclass
class UserMessage(Message):
    """User message."""
    role: MessageRole = field(default=MessageRole.USER, init=False)

    def __post_init__(self):
        self.role = MessageRole.USER


@dataclass
class AssistantMessage(Message):
    """Assistant message, may include tool calls."""
    role: MessageRole = field(default=MessageRole.ASSISTANT, init=False)
    tool_calls: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.role = MessageRole.ASSISTANT

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["tool_calls"] = self.tool_calls
        return d

    @classmethod
    def from_dict(cls, data: dict) -> AssistantMessage:
        return cls(
            content=data["content"],
            tool_calls=data.get("tool_calls", []),
            timestamp=datetime.fromisoformat(data.get("timestamp", _now().isoformat())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ToolMessage(Message):
    """Tool result message."""
    role: MessageRole = field(default=MessageRole.TOOL, init=False)
    tool_name: str = ""
    tool_call_id: str | None = None

    def __post_init__(self):
        self.role = MessageRole.TOOL

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["tool_name"] = self.tool_name
        d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ToolMessage:
        return cls(
            content=data["content"],
            tool_name=data.get("tool_name", ""),
            tool_call_id=data.get("tool_call_id"),
            timestamp=datetime.fromisoformat(data.get("timestamp", _now().isoformat())),
            metadata=data.get("metadata", {}),
        )