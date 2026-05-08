"""Plugin system for packaged yom integrations.

Plugins are coarse-grained, reusable add-ons. They can contribute tools,
providers, middleware, and lifecycle setup/teardown behavior. For simple
lifecycle callbacks use :mod:`yom.hooks`; for application-specific runtime
customization prefer direct composition until the experimental extension API is
stabilized.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from yom.providers import BaseProvider

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for yom plugins.

    Subclasses may override ``setup``/``teardown``. The older
    ``on_load``/``on_unload`` names are also supported for compatibility.
    """

    name: str = ""
    version: str = "1.0.0"
    description: str = ""

    def setup(self) -> None:
        """Called when plugin is loaded."""
        on_load = getattr(self, "on_load", None)
        if callable(on_load):
            on_load()

    def teardown(self) -> None:
        """Called when plugin is unloaded."""
        on_unload = getattr(self, "on_unload", None)
        if callable(on_unload):
            on_unload()


class ToolPlugin(Plugin):
    """Plugin that contributes tools."""

    def get_tools(self) -> list[Callable]:
        """Return tool callables provided by this plugin."""
        return []


class ProviderPlugin(Plugin):
    """Plugin that contributes one or more LLM providers."""

    def get_provider(self) -> "BaseProvider | None":
        """Return a default provider instance, if any."""
        return None

    def get_providers(self) -> dict[str, "BaseProvider"]:
        """Return named provider instances."""
        provider = self.get_provider()
        if provider is None:
            return {}
        name = getattr(provider, "provider_name", None) or self.name
        return {str(name): provider}


class MiddlewarePlugin(Plugin):
    """Plugin that contributes middleware callables.

    Middleware shape is intentionally simple: ``async fn(request, next_handler)``.
    The runtime does not apply middleware automatically yet; applications can
    retrieve them through ``YomApp.get_middleware()`` and compose them.
    """

    def get_middleware(self) -> list[Callable]:
        """Return middleware callables provided by this plugin."""
        return []


class ToolVersionRegistry:
    """Small registry for tracking plugin tool versions."""

    def __init__(self) -> None:
        self._versions: dict[str, str] = {}

    def register(self, tool_name: str, version: str) -> None:
        self._versions[tool_name] = version

    def get_version(self, tool_name: str) -> str | None:
        return self._versions.get(tool_name)

    def list_versions(self) -> dict[str, str]:
        return dict(self._versions)


class YomApp:
    """Application container for managing plugins.

    ``YomApp`` also acts as its own ``plugin_manager`` for compatibility with
    older examples that use ``app.plugin_manager.register_plugin(...)``.
    """

    def __init__(self):
        self._plugins: list[Plugin] = []

    @property
    def plugin_manager(self) -> "YomApp":
        return self

    def register_plugin(self, plugin: Plugin) -> None:
        """Register and initialize a plugin."""
        if not plugin.name:
            raise ValueError("Plugin.name is required")
        if plugin.name in self.list_plugins():
            raise ValueError(f"Plugin already registered: {plugin.name}")
        plugin.setup()
        self._plugins.append(plugin)
        logger.info("Registered plugin: %s v%s", plugin.name, plugin.version)

    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin by name."""
        for i, plugin in enumerate(self._plugins):
            if plugin.name == name:
                plugin.teardown()
                self._plugins.pop(i)
                logger.info("Unregistered plugin: %s", name)
                return True
        return False

    def get_tools(self) -> list[Callable]:
        """Get all tools from registered tool plugins."""
        tools: list[Callable] = []
        for plugin in self._plugins:
            if isinstance(plugin, ToolPlugin):
                tools.extend(plugin.get_tools())
        return tools

    def get_providers(self) -> dict[str, "BaseProvider"]:
        """Get all providers from registered provider plugins."""
        providers: dict[str, BaseProvider] = {}
        for plugin in self._plugins:
            if isinstance(plugin, ProviderPlugin):
                providers.update(plugin.get_providers())
        return providers

    def get_middleware(self) -> list[Callable]:
        """Get all middleware from registered middleware plugins."""
        middleware: list[Callable] = []
        for plugin in self._plugins:
            if isinstance(plugin, MiddlewarePlugin):
                middleware.extend(plugin.get_middleware())
        return middleware

    def list_plugins(self) -> list[str]:
        """List registered plugin names."""
        return [p.name for p in self._plugins]

    def load_plugins(self, directory: str | Path) -> int:
        """Load plugin instances from Python files in a directory.

        A plugin module may expose ``plugin`` as an instance, or ``plugins`` as a
        list of instances. Returns the number of loaded plugins.
        """
        directory = Path(directory)
        if not directory.exists():
            return 0

        loaded = 0
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = f"yom_plugin_{path.stem}_{abs(hash(path))}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            candidates: list[Any] = []
            if hasattr(module, "plugin"):
                candidates.append(module.plugin)
            if hasattr(module, "plugins"):
                candidates.extend(module.plugins)

            for candidate in candidates:
                if isinstance(candidate, Plugin):
                    self.register_plugin(candidate)
                    loaded += 1
        return loaded


class HotReloader:
    """Minimal polling hot-reloader for plugin directories.

    This intentionally keeps behavior conservative: on change it calls
    ``load_plugins``. Existing plugins are not forcibly unloaded because safe
    unload semantics are application-specific.
    """

    def __init__(self, plugin_manager: YomApp, directory: str | Path = "plugins", poll_interval: float = 5.0):
        self.plugin_manager = plugin_manager
        self.directory = Path(directory)
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._mtimes: dict[Path, float] = {}

    def _snapshot_changed(self) -> bool:
        files = {p: p.stat().st_mtime for p in self.directory.glob("*.py")} if self.directory.exists() else {}
        changed = files != self._mtimes
        self._mtimes = files
        return changed

    async def _watch(self) -> None:
        while self._running:
            if self._snapshot_changed():
                self.plugin_manager.load_plugins(self.directory)
            await asyncio.sleep(self.poll_interval)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._watch())
        except RuntimeError:
            # No running loop: do a one-shot load for synchronous callers.
            self.plugin_manager.load_plugins(self.directory)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None


__all__ = [
    "HotReloader",
    "MiddlewarePlugin",
    "Plugin",
    "ProviderPlugin",
    "ToolPlugin",
    "ToolVersionRegistry",
    "YomApp",
]
