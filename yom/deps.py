"""Runtime dependencies for AgentRuntime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass


StreamFn = Callable[..., object]


class RuntimeDeps(BaseModel):
    """Container for runtime dependencies."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_backend: Any = None
    tool_registry: Any = None
    context_manager: Any = None
    llm_stream: Any = None


class SessionManager:
    """Session manager placeholder for standalone mode."""
    pass


class ToolRegistry:
    """Tool registry placeholder for standalone mode."""
    pass
