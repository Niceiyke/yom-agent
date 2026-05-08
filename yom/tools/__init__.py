"""Tool interface and decorators."""

from yom.tools.adapter import ToolAdapter, to_yom_agent_registry
from yom.tools.core import (
    CORE_TOOL_NAMES,
    CORE_TOOLS,
    create_bash_tool,
    create_core_tools,
    create_edit_tool,
    create_glob_tool,
    create_grep_tool,
    create_read_tool,
    create_write_tool,
    get_tool,
)
from yom.tools.discover import load_tools_from_directory, merge_tool_registries
from yom.tools.protocol import Tool
from yom.tools.pydantic_tools import RunContext, agent_tool, tool
from yom.tools.registry import ToolRegistry
from yom.tools.result import ToolResult

__all__ = [
    # Core decorator
    "tool",
    "agent_tool",
    "RunContext",
    # Protocol and result
    "Tool",
    "ToolResult",
    # Registry
    "ToolRegistry",
    "ToolAdapter",
    "to_yom_agent_registry",
    # Core tools
    "CORE_TOOLS",
    "CORE_TOOL_NAMES",
    "get_tool",
    # Tool factories
    "create_core_tools",
    "create_read_tool",
    "create_write_tool",
    "create_edit_tool",
    "create_bash_tool",
    "create_grep_tool",
    "create_glob_tool",
    # Discovery
    "load_tools_from_directory",
    "merge_tool_registries",
]
