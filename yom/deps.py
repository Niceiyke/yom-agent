"""Runtime dependencies for AgentRuntime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from yom.tools import Tool
    from yom.models.state import AgentState
    from yom.session.backends import SessionBackend
    from yom.context.manager import ContextManager
    from yom.hooks.hooks import HookRegistry


StreamFn = Callable[..., object]


@dataclass
class RuntimeDeps:
    """Container for runtime dependencies."""
    session_backend: SessionBackend | None = None
    tool_registry: Tool | None = None
    context_manager: ContextManager | None = None
    llm_stream: StreamFn | None = None
    hooks: HookRegistry | None = None


class SessionManager:
    """Session manager placeholder for standalone mode."""
    pass


class ToolRegistry:
    """Tool registry placeholder for standalone mode."""
    pass
