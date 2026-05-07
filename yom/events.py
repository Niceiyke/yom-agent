"""Event types for agent runtime."""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class AgentEventType(Enum):
    """Enum of all agent events."""
    # Agent lifecycle
    AGENT_START = auto()
    AGENT_END = auto()
    
    # Turn lifecycle
    TURN_START = auto()
    TURN_END = auto()
    
    # Message lifecycle
    MESSAGE_START = auto()
    MESSAGE_END = auto()
    
    # Streaming
    MESSAGE_DELTA = auto()
    THINKING_DELTA = auto()
    
    # Tool lifecycle
    TOOL_START = auto()
    TOOL_END = auto()
    TOOL_RESULT = auto()
    
    # Error
    ERROR = auto()
    
    # Session
    SESSION_START = auto()
    SESSION_END = auto()
    
    # Queue updates
    QUEUE_UPDATE = auto()


@dataclass
class AgentEvent:
    """Base event class for all agent events."""
    type: AgentEventType
    data: dict[str, Any]
    
    @property
    def event_name(self) -> str:
        return self.type.name.lower()


@dataclass
class MessageDeltaEvent(AgentEvent):
    """Streaming text delta."""
    delta: str = ""
    
    def __post_init__(self):
        super().__init__(type=AgentEventType.MESSAGE_DELTA, data={"delta": self.delta})


@dataclass
class ToolStartEvent(AgentEvent):
    """Tool execution started."""
    tool_name: str = ""
    tool_args: dict[str, Any] | None = None
    
    def __post_init__(self):
        super().__init__(
            type=AgentEventType.TOOL_START, 
            data={"tool_name": self.tool_name, "tool_args": self.tool_args}
        )


@dataclass
class ToolEndEvent(AgentEvent):
    """Tool execution completed."""
    tool_name: str = ""
    result: str = ""
    error: str | None = None
    is_error: bool = False
    
    def __post_init__(self):
        super().__init__(
            type=AgentEventType.TOOL_END,
            data={
                "tool_name": self.tool_name,
                "result": self.result,
                "error": self.error,
                "is_error": self.is_error,
            }
        )


@dataclass
class TurnStartEvent(AgentEvent):
    """Turn started."""
    iteration: int = 0
    
    def __post_init__(self):
        super().__init__(type=AgentEventType.TURN_START, data={"iteration": self.iteration})


@dataclass
class TurnEndEvent(AgentEvent):
    """Turn completed."""
    iteration: int = 0
    response: str = ""
    tool_results: list[dict] | None = None
    
    def __post_init__(self):
        super().__init__(
            type=AgentEventType.TURN_END,
            data={
                "iteration": self.iteration,
                "response": self.response,
                "tool_results": self.tool_results or [],
            }
        )


@dataclass
class ErrorEvent(AgentEvent):
    """Error occurred."""
    error: str = ""
    
    def __post_init__(self):
        super().__init__(type=AgentEventType.ERROR, data={"error": self.error})


@dataclass
class AgentStartEvent(AgentEvent):
    """Agent started processing."""
    prompt: str = ""
    
    def __post_init__(self):
        super().__init__(type=AgentEventType.AGENT_START, data={"prompt": self.prompt})


@dataclass
class AgentEndEvent(AgentEvent):
    """Agent finished processing."""
    final_message: str = ""
    
    def __post_init__(self):
        super().__init__(type=AgentEventType.AGENT_END, data={"final_message": self.final_message})
