"""Dynamic tool discovery from Python files."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Iterator

from yom.tools.registry import ToolRegistry

TOOL_ATTR = "_tool_name"


def discover_tools_in_module(module) -> Iterator:
    """Yield tool-decorated functions from a module."""
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, TOOL_ATTR):
            yield obj


def load_tools_from_file(path: Path) -> list[Any]:
    """Load and return tools from a Python file."""
    tools: list[Any] = []
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        return tools

    module_name = f"yom.dynamic.{path.stem}"
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    for tool_func in discover_tools_in_module(module):
        tools.append(tool_func)

    return tools


def load_tools_from_directory(directory: str | Path) -> ToolRegistry:
    """Load all tools from Python files in a directory.

    Files should contain @tool decorated functions.

    Example:
        # .yom/tools/my_tool.py
        from yom.tools import tool

        @tool
        def my_tool(arg: str) -> str:
            '''My custom tool'''
            return f"Result: {arg}"

    Usage:
        registry = load_tools_from_directory(".yom/tools")
        agent = Agent(tools=registry.list())
    """
    registry = ToolRegistry()
    dir_path = Path(directory)

    if not dir_path.exists():
        return registry

    for path in sorted(dir_path.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            tools = load_tools_from_file(path)
            for tool_func in tools:
                registry.register(tool_func)
        except Exception as exc:
            print(f"Warning: Failed to load tools from {path}: {exc}")

    return registry


def merge_tool_registries(*registries: ToolRegistry) -> ToolRegistry:
    """Merge multiple tool registries into one."""
    merged = ToolRegistry()
    for reg in registries:
        for tool in reg.list():
            merged.register(tool)
    return merged
