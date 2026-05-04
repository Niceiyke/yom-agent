"""Tool protocol definition."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from yom.tools.result import ToolResult


@runtime_checkable
class Tool(Protocol):
    """Interface for agent tools."""

    @property
    def name(self) -> str:
        """Tool name, used in tool_calls from LLM."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description for LLM context."""
        ...

    @property
    def parameters(self) -> dict:
        """JSON Schema for tool parameters."""
        ...

    async def execute(self, **kwargs) -> "ToolResult":
        """Execute the tool with given parameters."""
        ...