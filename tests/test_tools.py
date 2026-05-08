"""Tests for tool system."""

from __future__ import annotations

import asyncio
import pytest

from yom.tools import (
    ToolRegistry,
    tool,
    ToolResult,
    CORE_TOOLS,
    CORE_TOOL_NAMES,
    get_tool,
)


class TestToolDecorator:
    """Tests for @tool decorator."""

    def test_basic_decorator(self):
        """Test basic @tool usage."""
        @tool
        def my_tool(arg1: str) -> str:
            """A test tool."""
            return f"Result: {arg1}"

        assert my_tool._tool_name == "my_tool"
        assert my_tool._tool_description == "A test tool."
        assert "properties" in my_tool._tool_parameters

    def test_custom_name_and_description(self):
        """Test custom name and description."""
        @tool(name="custom", description="Custom description")
        def some_func(x: int) -> str:
            return str(x)

        assert some_func._tool_name == "custom"
        assert some_func._tool_description == "Custom description"

    def test_schema_parameter(self):
        """Test explicit schema parameter."""
        @tool(schema={
            "type": "object",
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

        assert search._tool_name == "search"
        schema = search._tool_parameters
        assert "query" in schema["properties"]
        assert schema["properties"]["query"]["description"] == "Search query"

    def test_async_tool(self):
        """Test async tool function."""
        @tool
        async def async_tool(path: str) -> str:
            return f"Read: {path}"

        assert async_tool._tool_name == "async_tool"
        import inspect
        assert inspect.iscoroutinefunction(async_tool)


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        """Test basic register/get."""
        registry = ToolRegistry()

        @tool(name="test_tool")
        def test_func(x: str) -> str:
            return x

        registry.register(test_func)
        assert registry.get("test_tool") is test_func
        assert "test_tool" in registry

    def test_register_from_dict(self):
        """Test registering from dict definition."""
        registry = ToolRegistry()

        def my_func(x: str) -> str:
            return x

        schema = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"]
        }

        registry.register_from_dict("dict_tool", my_func, schema)

        assert registry.get("dict_tool") is my_func
        assert registry.get_schema("dict_tool") == schema

    def test_list_names(self):
        """Test listing tool names."""
        registry = ToolRegistry()

        @tool(name="tool1")
        def func1() -> str:
            return ""

        @tool(name="tool2")
        def func2() -> str:
            return ""

        registry.register(func1)
        registry.register(func2)

        names = registry.list_names()
        assert "tool1" in names
        assert "tool2" in names

    def test_schemas(self):
        """Test getting tool schemas."""
        registry = ToolRegistry()

        @tool(schema={
            "type": "object",
            "properties": {"x": {"type": "string"}}
        })
        def schema_tool(x: str) -> str:
            return x

        registry.register(schema_tool)
        schemas = registry.schemas()

        assert len(schemas) == 1
        assert schemas[0]["name"] == "schema_tool"

    def test_execute_success(self):
        """Test successful tool execution."""
        registry = ToolRegistry()

        @tool
        def add(x: int, y: int) -> str:
            return str(x + y)

        registry.register(add)

        result = asyncio.run(registry.execute("add", x=2, y=3))
        assert hasattr(result, 'is_success')
        assert result.content == "5"

    def test_execute_failure(self):
        """Test failed tool execution."""
        registry = ToolRegistry()

        @tool
        def failing_tool() -> str:
            raise ValueError("test error")

        registry.register(failing_tool)

        result = asyncio.run(registry.execute("failing_tool"))
        assert result.is_success is False
        assert "test error" in result.error

    def test_execute_not_found(self):
        """Test executing non-existent tool."""
        registry = ToolRegistry()

        result = asyncio.run(registry.execute("nonexistent"))
        assert result.is_success is False
        assert "not found" in result.error.lower()

    def test_unregister(self):
        """Test unregistering a tool."""
        registry = ToolRegistry()

        @tool(name="removable")
        def removable() -> str:
            return ""

        registry.register(removable)
        assert registry.get("removable") is removable

        registry.unregister("removable")
        assert registry.get("removable") is None

    def test_clear(self):
        """Test clearing registry."""
        registry = ToolRegistry()

        @tool(name="t1")
        def f1() -> str:
            return ""

        @tool(name="t2")
        def f2() -> str:
            return ""

        registry.register(f1)
        registry.register(f2)
        assert len(registry) == 2

        registry.clear()
        assert len(registry) == 0


class TestCoreTools:
    """Tests for core tools."""

    def test_core_tools_exist(self):
        """Test that core tools are available."""
        assert len(CORE_TOOLS) > 0

    def test_core_tool_names(self):
        """Test core tool names."""
        for name in ["read", "write", "edit", "bash", "cmd", "grep", "glob"]:
            assert name in CORE_TOOL_NAMES

    def test_get_tool(self):
        """Test getting core tool by name."""
        read_tool = get_tool("read")
        assert read_tool is not None
        assert read_tool._tool_name == "read"

    def test_get_tool_not_found(self):
        """Test getting non-existent tool."""
        assert get_tool("nonexistent") is None


class TestToolResult:
    """Tests for ToolResult."""

    def test_success_classmethod(self):
        """Test success factory method."""
        result = ToolResult.success("test", "content")
        assert result.is_success is True
        assert result.content == "content"
        assert result.error is None

    def test_failure_classmethod(self):
        """Test failure factory method."""
        result = ToolResult.failure("test", "error message")
        assert result.is_success is False
        assert result.content == ""
        assert result.error == "error message"

    def test_model_validation(self):
        """Test Pydantic model validation."""
        result = ToolResult(tool_name="test", content="hello")
        assert result.tool_name == "test"
        assert result.content == "hello"
        assert result.is_success is True
        assert result.error is None
