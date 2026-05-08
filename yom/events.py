"""Event types for agent runtime with Pydantic validation."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Self

from pydantic import BaseModel, Field


class AgentEventType(str, Enum):
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


class AgentEvent(BaseModel):
    """Base event class for all agent events."""
    type: AgentEventType
    data: dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"arbitrary_types_allowed": True}

    @property
    def event_name(self) -> str:
        return self.type.name.lower() if isinstance(self.type, AgentEventType) else str(self.type).lower()


class MessageDeltaEvent(AgentEvent):
    """Streaming text delta."""
    delta: str = ""
    
    def __init__(self, delta: str = "", **kwargs):
        super().__init__(
            type=AgentEventType.MESSAGE_DELTA, 
            data={"delta": delta, **kwargs.get("data", {})}
        )
        self.delta = delta


class ToolStartEvent(AgentEvent):
    """Tool execution started."""
    tool_name: str = ""
    tool_args: dict[str, Any] | None = None
    
    def __init__(self, tool_name: str = "", tool_args: dict[str, Any] | None = None, **kwargs):
        super().__init__(
            type=AgentEventType.TOOL_START, 
            data={"tool_name": tool_name, "tool_args": tool_args, **kwargs.get("data", {})}
        )
        self.tool_name = tool_name
        self.tool_args = tool_args


class ToolEndEvent(AgentEvent):
    """Tool execution completed."""
    tool_name: str = ""
    result: str = ""
    error: str | None = None
    is_error: bool = False
    
    def __init__(self, tool_name: str = "", result: str = "", error: str | None = None, is_error: bool = False, **kwargs):
        super().__init__(
            type=AgentEventType.TOOL_END,
            data={
                "tool_name": tool_name,
                "result": result,
                "error": error,
                "is_error": is_error,
                **kwargs.get("data", {})
            }
        )
        self.tool_name = tool_name
        self.result = result
        self.error = error
        self.is_error = is_error


class TurnStartEvent(AgentEvent):
    """Turn started."""
    iteration: int = 0
    
    def __init__(self, iteration: int = 0, **kwargs):
        super().__init__(
            type=AgentEventType.TURN_START, 
            data={"iteration": iteration, **kwargs.get("data", {})}
        )
        self.iteration = iteration


class TurnEndEvent(AgentEvent):
    """Turn completed."""
    iteration: int = 0
    response: str = ""
    tool_results: list[dict] | None = None
    
    def __init__(self, iteration: int = 0, response: str = "", tool_results: list[dict] | None = None, **kwargs):
        super().__init__(
            type=AgentEventType.TURN_END,
            data={
                "iteration": iteration,
                "response": response,
                "tool_results": tool_results or [],
                **kwargs.get("data", {})
            }
        )
        self.iteration = iteration
        self.response = response
        self.tool_results = tool_results


class ErrorEvent(AgentEvent):
    """Error occurred."""
    error: str = ""
    
    def __init__(self, error: str = "", **kwargs):
        super().__init__(
            type=AgentEventType.ERROR, 
            data={"error": error, **kwargs.get("data", {})}
        )
        self.error = error


class AgentStartEvent(AgentEvent):
    """Agent started processing."""
    prompt: str = ""
    
    def __init__(self, prompt: str = "", **kwargs):
        super().__init__(
            type=AgentEventType.AGENT_START, 
            data={"prompt": prompt, **kwargs.get("data", {})}
        )
        self.prompt = prompt


class AgentEndEvent(AgentEvent):
    """Agent finished processing."""
    final_message: str = ""
    
    def __init__(self, final_message: str = "", **kwargs):
        super().__init__(
            type=AgentEventType.AGENT_END, 
            data={"final_message": final_message, **kwargs.get("data", {})}
        )
        self.final_message = final_message
