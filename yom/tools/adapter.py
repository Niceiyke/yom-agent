"""Adapter for integrating with yom_agent's tool system."""

from __future__ import annotations

from typing import Any, Callable

from yom.tools.protocol import Tool
from yom.tools.result import ToolResult


class ToolAdapter:
    """Adapter that wraps agent-core Tool for yom_agent's ToolRegistry."""

    def __init__(self, tool: Tool | Callable):
        self._tool = tool

    @property
    def name(self) -> str:
        name = getattr(self._tool, "name", None)
        if name is not None:
            return name
        return getattr(self._tool, "_tool_name", "")

    @property
    def schema(self) -> dict[str, Any]:
        schema = getattr(self._tool, "_tool_parameters", None)
        if schema is not None:
            return schema
        return getattr(self._tool, "parameters", {})

    async def execute(self, input: dict[str, Any], state: Any) -> str:
        """Execute the tool and return string result."""
        tool = self._tool
        execute_fn = getattr(tool, "execute", None) or tool  # type: ignore[operator]

        try:
            result = execute_fn(**input)
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, ToolResult):
                return result.content
            return str(result)
        except Exception as e:
            return f"tool_error: {e}"


def to_yom_agent_registry(tools: list[Tool | Callable]) -> dict[str, Any]:
    """Convert agent-core tools to yom_agent's format."""
    result = {}
    for tool in tools:
        adapter = ToolAdapter(tool)
        result[adapter.name] = adapter
    return result


def from_yom_agent_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert yom_agent tool schemas to agent-core format."""
    return tools