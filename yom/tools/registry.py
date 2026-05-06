"""Tool registry for runtime."""

from __future__ import annotations

import logging
from typing import Callable

from yom.tools.protocol import Tool
from yom.tools.result import ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing tools available to a runtime.

    Usage:
        registry = ToolRegistry()
        registry.register(my_tool)

        tool = registry.get("tool_name")
        result = await registry.execute("tool_name", arg1="value")

        for schema in registry.schemas():
            print(schema)
    """

    def __init__(self):
        self._tools: dict[str, Tool | Callable] = {}
        self._schemas: dict[str, dict] = {}

    def register(self, tool: Tool | Callable, schema: dict | None = None) -> None:
        """Register a tool.

        Args:
            tool: Tool to register (must have name attribute or _tool_name)
            schema: Optional explicit JSON schema override
        """
        name = getattr(tool, "_tool_name", None) or getattr(tool, "name", None)
        if not name:
            raise ValueError(f"Tool has no name attribute: {tool}")

        self._tools[name] = tool

        if schema is not None:
            self._schemas[name] = schema
        elif hasattr(tool, "_tool_parameters"):
            self._schemas[name] = tool._tool_parameters
        elif hasattr(tool, "parameters"):
            self._schemas[name] = tool.parameters

        logger.debug(f"Registered tool: {name}")

    def register_from_dict(self, name: str, func: Callable, schema: dict) -> None:
        """Register a tool from a dict definition.

        Args:
            name: Tool name
            func: Callable tool function
            schema: JSON schema for parameters
        """
        if not hasattr(func, "_tool_name"):
            func._tool_name = name  # type: ignore[attr-defined]
        if not hasattr(func, "_tool_parameters"):
            func._tool_parameters = schema  # type: ignore[attr-defined]
        self._tools[name] = func
        self._schemas[name] = schema

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
        self._schemas.pop(name, None)
        logger.debug(f"Unregistered tool: {name}")

    def get(self, name: str) -> Tool | Callable | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list(self) -> list[Tool | Callable]:
        """"List all registered tools."""
        return list(self._tools.values()) # type: ignore[return-value]

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def schemas(self) -> list[dict]:
        """Get tool schemas for LLM."""
        schemas = []
        for name, schema in self._schemas.items():
            if schema:
                schema_with_name = dict(schema)
                if "name" not in schema_with_name:
                    schema_with_name["name"] = name
                schemas.append(schema_with_name)
        return schemas

    def get_schema(self, name: str) -> dict | None:
        """Get schema for a specific tool."""
        return self._schemas.get(name)

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            return ToolResult.from_failure(tool_name=name, error=f"Tool not found: {name}")

        try:
            execute_fn = getattr(tool, "execute", None) or tool  # type: ignore[operator]
            result = execute_fn(**kwargs)
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, ToolResult):
                return result
            return ToolResult.from_success(tool_name=name, content=str(result))
        except TypeError as e:
            return ToolResult.from_failure(tool_name=name, error=f"Invalid arguments: {e}")
        except Exception as e:
            logger.exception(f"Tool execution failed: {name}")
            return ToolResult.from_failure(tool_name=name, error=str(e))


    def clear(self) -> None:
        """Clear all tools."""
        self._tools.clear()
        self._schemas.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools