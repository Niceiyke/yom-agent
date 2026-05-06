"""Tool result type."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    tool_name: str
    content: str
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def from_success(cls, tool_name: str, content: str, **kwargs: Any) -> ToolResult:
        """Create a successful result."""
        return cls(tool_name=tool_name, content=content, success=True, **kwargs)

    @classmethod
    def from_failure(cls, tool_name: str, error: str, **kwargs: Any) -> ToolResult:
        """Create a failure result."""
        return cls(tool_name=tool_name, content="", success=False, error=error, **kwargs)