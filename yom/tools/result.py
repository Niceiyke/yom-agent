"""Tool result type with Pydantic validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Result returned by a tool execution with Pydantic validation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_name: str
    content: str = ""
    is_success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = None
    
    # Alias for backward compatibility
    @property
    def name(self) -> str:
        """Alias for tool_name for compatibility."""
        return self.tool_name
    @classmethod
    def from_success(cls, tool_name: str, content: str, **kwargs: Any) -> "ToolResult":
        """Create a successful result."""
        return cls(tool_name=tool_name, content=content, is_success=True, error=None, **kwargs)

    @classmethod
    def from_failure(cls, tool_name: str, error: str, **kwargs: Any) -> "ToolResult":
        """Create a failure result."""
        return cls(tool_name=tool_name, content="", is_success=False, error=error, **kwargs)
    
    # Keep old method names for compatibility
    @classmethod
    def success(cls, tool_name: str, content: str, **kwargs: Any) -> "ToolResult":
        return cls.from_success(tool_name, content, **kwargs)
    
    @classmethod
    def failure(cls, tool_name: str, error: str, **kwargs: Any) -> "ToolResult":
        return cls.from_failure(tool_name, error, **kwargs)
