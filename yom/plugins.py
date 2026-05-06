"""Plugin system for yom-agent.

Enables:
- Auto-loading of extensions
- Hot-reloading of tools
- Request/response middleware
- Dependency injection
- Tool versioning
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
import sys
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


# =============================================================================
# Plugin Interface
# =============================================================================

class Plugin(ABC):
    """Base class for yom plugins."""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""

    def setup(self, app: "YomApp") -> None:
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


class ProviderPlugin(Plugin):
    """Plugin that provides LLM providers."""

    def get_provider_factory(self) -> Callable[[], object]:
        """Return provider factory function."""
        return lambda: None  # type: ignore[return-value]


class MiddlewarePlugin(Plugin):
    """Plugin that provides middleware."""

    def get_middleware(self) -> list[Callable]:
        """Return list of middleware functions."""
        return []


# =============================================================================
# Middleware Types
# =============================================================================

Middleware = Callable[[dict, Callable], Awaitable[dict]]


async def default_middleware(request: dict, next_handler: Callable) -> dict:
    """Default middleware - just pass through."""
    return await next_handler(request)


@dataclass
class MiddlewareChain:
    """Chain of middleware to process requests/responses."""

    middlewares: list[Middleware] = field(default_factory=list)

    async def process(self, request: dict) -> dict:
        """Process request through middleware chain."""
        async def handler(req: dict) -> dict:
            return req

        for mw in reversed(self.middlewares):
            current_handler = handler
            async def wrapped(r: dict, h=current_handler) -> dict:  # type: ignore[assignment]
                return await mw(r, h)
            handler = wrapped  # type: ignore[assignment]

        return await handler(request)


# =============================================================================
# Tool Versioning
# =============================================================================

@dataclass
class ToolVersion:
    """Versioned tool with rollback support."""

    name: str
    func: Callable
    version: str
    rollback: Callable | None = None
    metadata: dict = field(default_factory=dict)


class ToolVersionRegistry:
    """Registry for versioned tools with rollback support."""

    def __init__(self):
        self._tools: dict[str, ToolVersion] = {}
        self._history: dict[str, list[ToolVersion]] = {}

    def register(
        self,
        name: str,
        func: Callable,
        version: str = "1.0.0",
        rollback: Callable | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a versioned tool."""
        tv = ToolVersion(
            name=name,
            func=func,
            version=version,
            rollback=rollback,
            metadata=metadata or {},
        )

        if name in self._tools:
            if name not in self._history:
                self._history[name] = []
            self._history[name].append(self._tools[name])

        self._tools[name] = tv
        logger.info(f"Registered tool '{name}' v{version}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool '{name}'")
            return True
        return False

    def get(self, name: str) -> ToolVersion | None:
        """Get latest version of a tool."""
        return self._tools.get(name)

    def list_versions(self, name: str) -> list[str]:
        """List all versions of a tool."""
        versions = []
        if name in self._tools:
            versions.append(self._tools[name].version)
        if name in self._history:
            versions.extend(v.version for v in self._history[name])
        return versions

    def rollback(self, name: str, target_version: str | None = None) -> bool:
        """Rollback to previous version."""
        if name not in self._history or not self._history[name]:
            return False

        if target_version is None:
            # Rollback to previous
            prev = self._history[name].pop()
            self._tools[name] = prev
            logger.info(f"Rolled back '{name}' to v{prev.version}")
            return True

        # Find specific version
        for i, tv in enumerate(self._history[name]):
            if tv.version == target_version:
                self._history[name].pop(i)
                self._tools[name] = tv
                logger.info(f"Rolled back '{name}' to v{tv.version}")
                return True
        return False


# =============================================================================
# Plugin Manager
# =============================================================================

@dataclass
class PluginInfo:
    """Information about a loaded plugin."""

    name: str
    version: str
    description: str
    instance: Plugin
    loaded_at: float


class PluginManager:
    """Manages plugins with auto-discovery and hot-reload."""

    def __init__(self, app: "YomApp"):
        self.app = app
        self._plugins: dict[str, PluginInfo] = {}
        self._tool_registry = ToolVersionRegistry()
        self._middleware = MiddlewareChain()
        self._file_watchers: dict[str, float] = {}

    def register_plugin(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        if not plugin.name:
            raise ValueError("Plugin must have a name")

        plugin.setup(self.app)
        self._plugins[plugin.name] = PluginInfo(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            instance=plugin,
            loaded_at=asyncio.get_event_loop().time(),
        )
        logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")

        # Extract tools
        if isinstance(plugin, ToolPlugin):
            for tool in plugin.get_tools():
                tool_name: str = getattr(tool, "_tool_name", None) or getattr(tool, "__name__", "unknown")
                if tool_name:
                    self._tool_registry.register(tool_name, tool)

        # Extract middleware
        if isinstance(plugin, MiddlewarePlugin):
            for mw in plugin.get_middleware():
                self._middleware.middlewares.append(mw)

    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin."""
        if name in self._plugins:
            self._plugins[name].instance.teardown()
            del self._plugins[name]
            logger.info(f"Unloaded plugin: {name}")
            return True
        return False

    def get_plugin(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        info = self._plugins.get(name)
        return info.instance if info else None

    def list_plugins(self) -> list[PluginInfo]:
        """List all loaded plugins."""
        return list(self._plugins.values())

    @property
    def tool_registry(self) -> ToolVersionRegistry:
        """Get tool registry."""
        return self._tool_registry

    @property
    def middleware(self) -> MiddlewareChain:
        """Get middleware chain."""
        return self._middleware


# =============================================================================
# Auto-Discovery
# =============================================================================

class PluginDiscovery:
    """Discovers plugins from various sources."""

    @staticmethod
    def from_directory(path: str | Path, pattern: str = "*.py") -> list[type]:
        """Discover plugins from a directory."""
        path = Path(path)
        if not path.exists():
            return []

        plugins = []
        for file in path.glob(pattern):
            if file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[file.stem] = module
                    spec.loader.exec_module(module)

                    # Look for Plugin subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                            plugins.append(attr)
            except Exception as e:
                logger.warning(f"Failed to load plugin from {file}: {e}")

        return plugins

    @staticmethod
    def from_package(package_name: str) -> list[type]:
        """Discover plugins from an installed package."""
        try:
            spec = importlib.util.find_spec(package_name)
            if spec is None or spec.submodule_search_locations is None:
                return []
            pkg_path = Path(spec.submodule_search_locations[0])
            return PluginDiscovery.from_directory(pkg_path)
        except Exception as e:
            logger.warning(f"Failed to discover plugins from {package_name}: {e}")
            return []

    @staticmethod
    def from_entry_points(group: str = "yom.plugins") -> list[Plugin]:
        """Discover plugins from package entry points."""
        try:
            from importlib.metadata import entry_points
            eps = entry_points()
            plugins = []
            # Handle different Python versions' entry_points API
            if hasattr(eps, "get"):
                entries = eps.get(group, [])
            else:
                # Python 3.10+ uses SelectableGroups
                entries = list(eps.select(group=group))  # type: ignore[var-annotated, union-attr]
            for ep in entries:
                try:
                    plugin_class = ep.load()
                    plugins.append(plugin_class())
                except Exception as e:
                    logger.warning(f"Failed to load plugin {ep.name}: {e}")
            return plugins
        except Exception as e:
            logger.warning(f"Failed to discover entry points: {e}")
            return []


# =============================================================================
# Hot Reload
# =============================================================================

class HotReloader:
    """Watches files and reloads on changes."""

    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self._watch_paths: dict[Path, float] = {}
        self._running = False

    def watch_directory(self, path: str | Path, pattern: str = "*.py") -> None:
        """Watch a directory for changes."""
        path = Path(path)
        if not path.exists():
            return

        for file in path.glob(pattern):
            if file.name.startswith("_"):
                continue
            self._watch_paths[file] = file.stat().st_mtime

    async def check_changes(self) -> list[Path]:
        """Check for file changes and return modified files."""
        modified = []
        for file, last_mtime in list(self._watch_paths.items()):
            try:
                current_mtime = file.stat().st_mtime
                if current_mtime > last_mtime:
                    modified.append(file)
                    self._watch_paths[file] = current_mtime
            except FileNotFoundError:
                del self._watch_paths[file]
        return modified

    async def reload_modified(self) -> int:
        """Reload plugins for modified files."""
        modified = await self.check_changes()
        reloaded = 0

        for file in modified:
            logger.info(f"Reloading modified file: {file}")
            try:
                # Invalidate module cache
                module_name = file.stem
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])

                # Re-discover and reload plugins
                for attr_name in dir(sys.modules[module_name]):
                    attr = getattr(sys.modules[module_name], attr_name)
                    if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                        # Unload old, load new
                        if attr.name in self.plugin_manager._plugins:
                            self.plugin_manager.unregister_plugin(attr.name)
                        self.plugin_manager.register_plugin(attr())
                        reloaded += 1

            except Exception as e:
                logger.error(f"Failed to reload {file}: {e}")

        if reloaded:
            logger.info(f"Reloaded {reloaded} plugins")

        return reloaded

    async def watch_loop(self, interval: float = 1.0) -> None:
        """Start watching for changes."""
        self._running = True
        while self._running:
            await self.reload_modified()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Stop watching."""
        self._running = False


# =============================================================================
# Dependency Injection Container
# =============================================================================

class Container:
    """Simple dependency injection container."""

    def __init__(self):
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable] = {}
        self._singletons: set[type] = set()

    def register(
        self,
        service_type: type,
        instance: Any = None,
        factory: Callable | None = None,
        singleton: bool = True,
    ) -> None:
        """Register a service."""
        if instance is not None:
            self._services[service_type] = instance
            if singleton:
                self._singletons.add(service_type)
        elif factory is not None:
            self._factories[service_type] = factory
            if singleton:
                self._singletons.add(service_type)
        else:
            raise ValueError("Must provide either instance or factory")

    def get(self, service_type: type) -> Any:
        """Get a service instance."""
        if service_type in self._services and service_type not in self._singletons:
            # Return a new instance for non-singletons
            if callable(self._services[service_type]):
                return self._services[service_type]()
            return self._services[service_type]

        if service_type in self._services:
            return self._services[service_type]

        if service_type in self._factories:
            instance = self._factories[service_type]()
            if service_type in self._singletons:
                self._services[service_type] = instance
            return instance

        raise KeyError(f"Service {service_type} not registered")

    def has(self, service_type: type) -> bool:
        """Check if service is registered."""
        return service_type in self._services or service_type in self._factories


# =============================================================================
# Main Application
# =============================================================================

class YomApp:
    """Main yom application with plugin support."""

    def __init__(self):
        self.plugin_manager = PluginManager(self)
        self.container = Container()
        self._hot_reloader: HotReloader | None = None

    def load_plugins_from_directory(self, path: str | Path) -> int:
        """Load all plugins from a directory."""
        plugin_classes = PluginDiscovery.from_directory(path)
        for cls in plugin_classes:
            try:
                self.plugin_manager.register_plugin(cls())
            except Exception as e:
                logger.error(f"Failed to load plugin {cls}: {e}")
        return len(plugin_classes)

    def load_plugins_from_package(self, package_name: str) -> int:
        """Load plugins from an installed package."""
        plugin_classes = PluginDiscovery.from_package(package_name)
        for cls in plugin_classes:
            try:
                self.plugin_manager.register_plugin(cls())
            except Exception as e:
                logger.error(f"Failed to load plugin {cls}: {e}")
        return len(plugin_classes)

    def load_plugins_from_entry_points(self, group: str = "yom.plugins") -> int:
        """Load plugins from entry points."""
        plugins = PluginDiscovery.from_entry_points(group)
        for plugin in plugins:
            try:
                self.plugin_manager.register_plugin(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin {e}: {e}")
        return len(plugins)

    def enable_hot_reload(self, directories: list[str | Path]) -> None:
        """Enable hot-reload for plugin directories."""
        self._hot_reloader = HotReloader(self.plugin_manager)
        for directory in directories:
            self._hot_reloader.watch_directory(directory)

    async def start_hot_reload(self, interval: float = 1.0) -> None:
        """Start the hot-reload watcher."""
        if self._hot_reloader:
            await self._hot_reloader.watch_loop(interval)

    def stop_hot_reload(self) -> None:
        """Stop the hot-reload watcher."""
        if self._hot_reloader:
            self._hot_reloader.stop()
            self._hot_reloader = None

    def process_middleware(self, request: dict) -> Awaitable[dict]:
        """Process request through middleware chain."""
        return self.plugin_manager.middleware.process(request)


# =============================================================================
# Example Plugin
# =============================================================================

"""
Example plugin file: my_plugin.py

from yom.plugins import Plugin, ToolPlugin, MiddlewarePlugin, YomApp
from yom import tool

class MyToolsPlugin(ToolPlugin):
    name = "my-tools"
    version = "1.0.0"
    description = "My custom tools"
    
    def get_tools(self):
        return [my_custom_tool]

@tool(name="my_custom_tool")
def my_custom_tool(param: str) -> str:
    return f"Custom: {param}"

class MyMiddlewarePlugin(MiddlewarePlugin):
    name = "my-middleware"
    version = "1.0.0"
    description = "Request/response middleware"
    
    def get_middleware(self):
        return [my_logging_middleware]

async def my_logging_middleware(request, next_handler):
    print(f"Request: {request}")
    result = await next_handler(request)
    print(f"Response: {result}")
    return result
"""

__all__ = [
    "Plugin",
    "ToolPlugin", 
    "ProviderPlugin",
    "MiddlewarePlugin",
    "PluginManager",
    "PluginInfo",
    "PluginDiscovery",
    "HotReloader",
    "ToolVersionRegistry",
    "ToolVersion",
    "MiddlewareChain",
    "Container",
    "YomApp",
]
