"""Runtime dependencies for AgentRuntime."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from yom.tools import Tool
    from yom.models import AgentState
    from yom.session import SessionBackend
    from yom.context import ContextManager


StreamFn = Callable[..., object]


@dataclass
class RuntimeDeps:
    """Container for runtime dependencies."""
    session_backend: SessionBackend | None = None
    hooks: "HookRegistry" = field(default_factory=lambda: __import__("yom.hooks", fromlist=["HookRegistry"]).HookRegistry())
    tool_registry: ToolRegistry | None = None
    subagents: SubAgentManager = field(default_factory=lambda: __import__("yom.subagent.core", fromlist=["SubAgentManager"]).SubAgentManager())
    llm_stream: StreamFn | None = None
    context_manager: ContextManager | None = None


class SessionManager:
    """Session manager placeholder for standalone mode."""
    pass


class ToolRegistry:
    """Tool registry placeholder for standalone mode."""
    pass


class SubAgentManager:
    """Sub-agent manager placeholder for standalone mode."""
    pass
