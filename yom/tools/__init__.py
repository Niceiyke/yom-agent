"""Tool interface and decorators."""

from yom.tools.pydantic_tools import tool, agent_tool, RunContext
from yom.tools.protocol import Tool
from yom.tools.result import ToolResult
from yom.tools.registry import ToolRegistry
from yom.tools.adapter import ToolAdapter, to_yom_agent_registry
from yom.tools.core import (
    CORE_TOOLS, 
    CORE_TOOL_NAMES, 
    get_tool,
    create_core_tools,
    create_read_tool,
    create_write_tool,
    create_edit_tool,
    create_bash_tool,
    create_grep_tool,
    create_glob_tool,
)
from yom.tools.discover import load_tools_from_directory, merge_tool_registries

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
    # Tool definition helpers
    "define_tool",
    "create_tool",
    # Discovery
    "load_tools_from_directory",
    "merge_tool_registries",
]
