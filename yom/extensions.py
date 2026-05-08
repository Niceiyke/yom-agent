"""Extension points for agent-core runtime.

This module defines the interfaces that users can implement
to extend the runtime behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from yom.agent_runtime import AgentRuntime
    from yom.models.state import AgentState


class RuntimeExtension(ABC):
    """Base class for runtime extensions."""

    @abstractmethod
    def on_initialized(self, runtime: AgentRuntime) -> None:
        """Called when the runtime is initialized."""
        pass

    @abstractmethod
    def on_shutdown(self) -> None:
        """Called when the runtime is shutting down."""
        pass


class TurnHook(ABC):
    """Hook called before and after each agent turn."""

    @abstractmethod
    async def before_turn(self, state: AgentState) -> None:
        """Called before a turn executes."""
        pass

    @abstractmethod
    async def after_turn(self, state: AgentState, response: str) -> None:
        """Called after a turn completes."""
        pass


class ToolHook(ABC):
    """Hook called before and after tool execution."""

    @abstractmethod
    async def before_tool(self, tool_name: str, input: dict[str, Any]) -> None:
        """Called before a tool executes."""
        pass

    @abstractmethod
    async def after_tool(self, tool_name: str, result: str) -> None:
        """Called after a tool executes."""
        pass


class SessionHook(ABC):
    """Hook called on session lifecycle events."""

    @abstractmethod
    async def on_session_start(self, session_id: str, state: AgentState) -> None:
        """Called when a session starts."""
        pass

    @abstractmethod
    async def on_session_end(self, session_id: str) -> None:
        """Called when a session ends."""
        pass


class ErrorHandler(ABC):
    """Handler for runtime errors."""

    @abstractmethod
    async def on_error(self, error: Exception, state: AgentState | None) -> None:
        """Called when an error occurs."""
        pass


# Type aliases for simpler extension
CallbackHook = Callable[[dict[str, Any]], Awaitable[None]]
Middleware = Callable[[dict[str, Any], Callable], Awaitable[dict[str, Any]]]
