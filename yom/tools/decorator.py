"""@tool decorator for simple function-based tools."""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, TypeVar, overload

from yom.tools.result import ToolResult

F = TypeVar("F", bound=Callable)


class ToolDecorator:
    """Helper to build tool metadata from decorated function."""

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        parameters: dict | None = None,
        schema: dict | None = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.schema = schema

    def __call__(self, func: F) -> F:
        is_async = inspect.iscoroutinefunction(func)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                raise TypeError(
                    f"@tool decorated function '{func.__name__}' is async, "
                    "use async def or apply @async_tool decorator"
                )
            tool_name = self.name or func.__name__
            if isinstance(result, ToolResult):
                result.tool_name = tool_name
                return result
            return ToolResult(tool_name=tool_name, content=str(result))

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            tool_name = self.name or func.__name__
            if isinstance(result, ToolResult):
                result.tool_name = tool_name
                return result
            return ToolResult(tool_name=tool_name, content=str(result))

        desc = self.description
        if desc is None:
            desc = func.__doc__ or f"Tool: {func.__name__}"
        desc = desc.strip()

        params = self._build_parameters(func)

        wrapper = async_wrapper if is_async else sync_wrapper
        wrapper._tool_name = self.name or func.__name__
        wrapper._tool_description = desc
        wrapper._tool_parameters = params
        wrapper._tool_func = func
        wrapper._tool_schema_version = "1.0"

        return wrapper

    def _build_parameters(self, func: Callable) -> dict:
        """Build parameters schema, using explicit schema if provided."""
        if self.schema is not None:
            return self._normalize_schema(self.schema)
        if self.parameters is not None:
            return self._normalize_schema(self.parameters)
        return self._build_from_signature(func)

    def _normalize_schema(self, schema: dict) -> dict:
        """Normalize schema to always have properties wrapper."""
        if "properties" in schema:
            return schema
        return {"type": "object", "properties": schema}

    def _build_from_signature(self, func: Callable) -> dict:
        """Build parameters schema from function signature."""
        sig = inspect.signature(func)
        props = {}
        required = []
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        for pname, param in sig.parameters.items():
            ann = param.annotation
            prop = {}
            if ann != inspect.Parameter.empty and ann in type_map:
                prop["type"] = type_map[ann]
            else:
                prop["type"] = "string"

            if param.default is not inspect.Parameter.empty:
                prop["default"] = param.default
            else:
                required.append(pname)

            props[pname] = prop

        return {
            "type": "object",
            "properties": props,
            "required": required,
        }


@overload
def tool(func: F) -> F: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict | None = None,
    schema: dict | None = None,
) -> Callable[[F], F]: ...


def tool(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict | None = None,
    schema: dict | None = None,
) -> F | Callable[[F], F]:
    """
    Decorator to mark a function as an agent tool.

    Usage:
        @tool
        def get_weather(location: str) -> str:
            '''Get weather for a location'''
            return f"Weather in {location}: sunny"

        @tool(name="custom_name", description="Custom description")
        def my_tool(arg1: str) -> str:
            return f"Result: {arg1}"

        @tool(schema={
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        })
        def search(query: str) -> str:
            return f"Results for: {query}"
    """
    if func is not None:
        return ToolDecorator()(func)
    return ToolDecorator(name=name, description=description, parameters=parameters, schema=schema)