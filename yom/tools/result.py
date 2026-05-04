"""Tool result type."""

from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    tool_name: str
    content: str
    success: bool = True
    error: str | None = None
    metadata: dict | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def success(cls, tool_name: str, content: str, **kwargs):
        return cls(tool_name=tool_name, content=content, success=True, **kwargs)

    @classmethod
    def failure(cls, tool_name: str, error: str, **kwargs):
        return cls(tool_name=tool_name, content="", success=False, error=error, **kwargs)