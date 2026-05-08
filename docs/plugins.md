# Plugins

**Hot-reloadable extensions for yom.**

Plugins let you add tools, providers, and middleware without modifying yom's core.

## Overview

```
┌─────────────────────────────────────────┐
│                YomApp                   │
│  ┌───────────────────────────────────┐ │
│  │        PluginManager              │ │
│  │  ┌─────────┐ ┌─────────┐        │ │
│  │  │ Plugin1 │ │ Plugin2 │ ...     │ │
│  │  └─────────┘ └─────────┘        │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│         Agent (with plugin tools)        │
└─────────────────────────────────────────┘
```

## Creating Plugins

### Base Plugin

```python
from yom.plugins import Plugin

class MyPlugin(Plugin):
    name = "my-plugin"
    version = "1.0.0"
    
    def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass
    
    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass
```

### Tool Plugin

```python
from yom.plugins import ToolPlugin
from yom import tool

class MathPlugin(ToolPlugin):
    name = "math"
    
    @staticmethod
    @tool(name="calculate", description="Perform a calculation")
    def calculate(expression: str) -> str:
        """Evaluate a mathematical expression."""
        import ast
        try:
            result = ast.literal_eval(expression)
            return str(result)
        except Exception as e:
            return f"Error: {e}"
    
    def get_tools(self):
        return [self.calculate]
```

### Provider Plugin

```python
from yom.plugins import ProviderPlugin
from yom.providers import BaseProvider

class CustomProvider(BaseProvider):
    def complete(self, messages, model, config):
        # Your implementation
        ...
    
    def stream(self, messages, model, config):
        # Your implementation
        ...

class MyProviderPlugin(ProviderPlugin):
    name = "my-provider"
    
    def get_provider(self) -> BaseProvider:
        return CustomProvider()
```

### Middleware Plugin

```python
from yom.plugins import MiddlewarePlugin

class LoggingMiddleware(MiddlewarePlugin):
    name = "logging-middleware"
    
    async def process_message(self, message: dict) -> dict:
        print(f"Processing: {message}")
        return message
    
    async def process_response(self, response: str) -> str:
        print(f"Response: {response[:100]}...")
        return response
```

## Registering Plugins

### Manual Registration

```python
from yom.plugins import YomApp

app = YomApp()
app.plugin_manager.register_plugin(MathPlugin())
```

### Auto-Discovery

```python
# Load all plugins from directory
app = YomApp()
app.plugin_manager.load_plugins("./plugins")
```

## Plugin Structure

### Directory Layout

```
plugins/
├── my-plugin/
│   ├── __init__.py
│   └── tools.py
├── math-plugin/
│   ├── __init__.py
│   ├── provider.py
│   └── middleware.py
└── config.yaml
```

### `__init__.py`

```python
from my_plugin.tools import MathPlugin

__all__ = [MathPlugin]
```

### Config File

**`plugins/config.yaml`**
```yaml
plugins:
  - name: math
    enabled: true
    options:
      precision: 10
  
  - name: my-provider
    enabled: true
    options:
      api_key: "${MY_API_KEY}"
```

## Hot Reloading

Plugins can be reloaded without restarting:

```python
from yom.plugins import YomApp, HotReloader

app = YomApp()

# Enable file watching
reloader = HotReloader(app.plugin_manager, poll_interval=5.0)

# Watch for changes
reloader.start()
# ... plugins reload on file change ...

# Stop watching
reloader.stop()
```

## Tool Versioning

Track tool versions across plugins:

```python
from yom.plugins import ToolVersionRegistry

registry = ToolVersionRegistry()

# Register a version
registry.register("math.calculate", "1.0.0")

# Check versions
version = registry.get_version("math.calculate")
print(f"math.calculate version: {version}")
```

## Built-in Plugins

yom includes several built-in toolsets:

### Core Tools

```python
from yom.toolsets import CORE_TOOLS
# read, write, edit, bash, glob, grep
```

### HTTP Tools

```python
from yom.toolsets import http_request, get_json

agent = Agent(tools=["http_request", "get_json"])
```

### Shell Tools

```python
from yom.toolsets import shell, shell_script

agent = Agent(tools=["shell"])
```

### GitHub Tools

```python
from yom.toolsets import github_api, github_read_file, github_search

agent = Agent(tools=["github_api"])
```

### S3 Tools

```python
from yom.toolsets import s3_put, s3_get, s3_list

agent = Agent(tools=["s3_put", "s3_get", "s3_list"])
```

## Dependency Injection

Plugins can access agent context:

```python
class DatabasePlugin(ToolPlugin):
    name = "database"
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    @tool
    def query_db(self, sql: str) -> str:
        """Run a SQL query."""
        # Use self.connection_string
        ...
```

## Example: Custom API Plugin

### 1. Create plugin

**`plugins/api-client/__init__.py`**
```python
from yom.plugins import ToolPlugin
from yom import tool
import httpx

class ApiClientPlugin(ToolPlugin):
    name = "api-client"
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
    
    @tool(name="api_get", description="Make GET request to API")
    def api_get(self, path: str) -> str:
        """Make a GET request."""
        response = httpx.get(
            f"{self.base_url}{path}",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.text
    
    @tool(name="api_post", description="Make POST request to API")
    def api_post(self, path: str, data: str) -> str:
        """Make a POST request."""
        response = httpx.post(
            f"{self.base_url}{path}",
            json={"data": data},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.text
    
    def get_tools(self):
        return [self.api_get, self.api_post]
```

### 2. Use it

```python
from yom import Agent
from yom.plugins import YomApp

app = YomApp()
app.plugin_manager.register_plugin(
    ApiClientPlugin(
        base_url="https://api.example.com",
        api_key="secret"
    )
)

# Get tools from plugin
tools = app.plugin_manager.get_tools()
agent = Agent(tools=tools)
```

### 3. Install

```bash
# Package and distribute
pip install my-api-client-plugin

# Or load from path
app.plugin_manager.load_plugins("/path/to/plugins")
```

## Security

### Sandboxing

Tools run in the agent's context. Consider sandboxing sensitive operations:

```python
class SensitivePlugin(ToolPlugin):
    name = "sensitive"
    
    @tool(name="delete_file")
    def delete_file(self, path: str) -> str:
        # Validate path
        if not path.startswith("/safe/directory"):
            return "Error: Path not allowed"
        # Proceed with deletion
        ...
```

### Hook Integration

Use hooks to control plugin tools:

```python
from yom import global_hooks, allow, block

# Block sensitive operations
global_hooks.register("delete_file", block(reason="Not allowed"))
```

## Testing Plugins

```python
import pytest

def test_my_plugin():
    from my_plugin import MathPlugin
    
    plugin = MathPlugin()
    result = plugin.calculate("2 + 2")
    
    assert result == "4"
```

## Best Practices

1. **Keep plugins focused** - One responsibility per plugin
2. **Use type hints** - For tool parameters and return types
3. **Handle errors gracefully** - Return meaningful error messages
4. **Document tools** - Clear descriptions help the LLM
5. **Version your plugins** - For compatibility tracking
6. **Test tools in isolation** - Unit test each tool function
