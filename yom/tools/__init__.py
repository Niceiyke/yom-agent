"""Tool interface and decorators."""

from yom.tools.decorator import tool
from yom.tools.protocol import Tool
from yom.tools.result import ToolResult
from yom.tools.registry import ToolRegistry
from yom.tools.adapter import ToolAdapter, to_yom_agent_registry
from yom.tools.core import CORE_TOOLS, CORE_TOOL_NAMES, get_tool
from yom.tools.discover import load_tools_from_directory, merge_tool_registries

__all__ = [
    "tool",
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "ToolAdapter",
    "to_yom_agent_registry",
    "CORE_TOOLS",
    "CORE_TOOL_NAMES",
    "get_tool",
    "load_tools_from_directory",
    "merge_tool_registries",
]