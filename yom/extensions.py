"""Experimental runtime extension interfaces.

Use these only for application-specific experiments. Stable customization APIs:

- :mod:`yom.hooks` / ``Agent.subscribe`` for lifecycle callbacks.
- :mod:`yom.plugins` for packaged reusable integrations.

The extension API is intentionally not exported from ``yom.__init__`` and may
change before a stable release.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from yom.agent_runtime import AgentRuntime
    from yom.models.state import AgentState


class RuntimeExtension(ABC):
    """Experimental base class for runtime-level extensions."""

    experimental = True

    @abstractmethod
    def on_initialized(self, runtime: AgentRuntime) -> None:
        """Called when the runtime is initialized."""
        pass

    @abstractmethod
    def on_shutdown(self) -> None:
        """Called when the runtime is shutting down."""
        pass


class TurnHook(ABC):
    """Experimental turn extension interface.

    Prefer :class:`yom.hooks.HookRegistry` or ``Agent.subscribe`` for stable
    lifecycle callbacks.
    """

    experimental = True

    @abstractmethod
    async def before_turn(self, state: AgentState) -> None:
        """Called before a turn executes."""
        pass

    @abstractmethod
    async def after_turn(self, state: AgentState, response: str) -> None:
        """Called after a turn completes."""
        pass


class ToolHook(ABC):
    """Experimental tool extension interface."""

    experimental = True

    @abstractmethod
    async def before_tool(self, tool_name: str, input: dict[str, Any]) -> None:
        """Called before a tool executes."""
        pass

    @abstractmethod
    async def after_tool(self, tool_name: str, result: str) -> None:
        """Called after a tool executes."""
        pass


class SessionHook(ABC):
    """Experimental session extension interface."""

    experimental = True

    @abstractmethod
    async def on_session_start(self, session_id: str, state: AgentState) -> None:
        """Called when a session starts."""
        pass

    @abstractmethod
    async def on_session_end(self, session_id: str) -> None:
        """Called when a session ends."""
        pass


class ErrorHandler(ABC):
    """Experimental runtime error extension interface."""

    experimental = True

    @abstractmethod
    async def on_error(self, error: Exception, state: AgentState | None) -> None:
        """Called when an error occurs."""
        pass


CallbackHook = Callable[[dict[str, Any]], Awaitable[None]]
Middleware = Callable[[dict[str, Any], Callable], Awaitable[dict[str, Any]]]


__all__ = [
    "CallbackHook",
    "ErrorHandler",
    "Middleware",
    "RuntimeExtension",
    "SessionHook",
    "ToolHook",
    "TurnHook",
]
