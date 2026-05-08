"""Simple plugin system for yom-agent."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for yom plugins."""

    name: str = ""
    version: str = "1.0.0"

    def setup(self) -> None:
        """Called when plugin is loaded."""
        pass

    def teardown(self) -> None:
        """Called when plugin is unloaded."""
        pass


class ToolPlugin(Plugin):
    """Plugin that provides tools."""

    def get_tools(self) -> list[Callable]:
        """Return list of tool functions."""
        return []


class YomApp:
    """Simple application container for managing plugins."""

    def __init__(self):
        self._plugins: list[Plugin] = []

    def register_plugin(self, plugin: Plugin) -> None:
        """Register a plugin."""
        plugin.setup()
        self._plugins.append(plugin)
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin by name."""
        for i, plugin in enumerate(self._plugins):
            if plugin.name == name:
                plugin.teardown()
                self._plugins.pop(i)
                return True
        return False

    def get_tools(self) -> list[Callable]:
        """Get all tools from registered plugins."""
        tools = []
        for plugin in self._plugins:
            if isinstance(plugin, ToolPlugin):
                tools.extend(plugin.get_tools())
        return tools

    def list_plugins(self) -> list[str]:
        """List registered plugin names."""
        return [p.name for p in self._plugins]


__all__ = [
    "Plugin",
    "ToolPlugin",
    "YomApp",
]
