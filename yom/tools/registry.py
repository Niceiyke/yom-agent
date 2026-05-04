"""Tool registry for runtime."""

from typing import Callable

from yom.tools.protocol import Tool
from yom.tools.result import ToolResult


class ToolRegistry:
    """Registry for managing tools available to a runtime."""

    def __init__(self):
        self._tools: dict[str, Tool | Callable] = {}

    def register(self, tool: Tool | Callable) -> None:
        """Register a tool."""
        name = getattr(tool, "name", None) or getattr(tool, "_tool_name", None)
        if not name:
            raise ValueError(f"Tool has no name attribute: {tool}")
        self._tools[name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | Callable | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list(self) -> list[Tool | Callable]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def schemas(self) -> list[dict]:
        """Get tool schemas for LLM."""
        schemas = []
        for tool in self._tools.values():
            schema = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", None)
            if schema:
                schemas.append(schema)
        return schemas

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult.failure(tool_name=name, error=f"Tool not found: {name}")

        try:
            execute_fn = getattr(tool, "execute", None) or tool
            result = execute_fn(**kwargs)
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, ToolResult):
                return result
            return ToolResult.success(tool_name=name, content=str(result))
        except Exception as e:
            return ToolResult.failure(tool_name=name, error=str(e))

    def clear(self) -> None:
        """Clear all tools."""
        self._tools.clear()