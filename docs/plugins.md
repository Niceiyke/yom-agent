# Plugins, Hooks, and Extensions

This page defines the customization layers in yom.

## Quick distinction

| API | Stability | Scope | Use for |
|---|---:|---|---|
| Hooks / `Agent.subscribe` | Stable | Small callbacks | logging, metrics, audit, tracing |
| Plugins | Stable-ish | Packaged integrations | reusable tools, providers, middleware bundles |
| Extensions | Experimental | Runtime behavior changes | app-specific experiments only |

## Hooks

Hooks are callbacks at known lifecycle points. Use them when you want to react to
something yom is already doing.

```python
from yom import Agent

agent = Agent(tools=["core"])

unsub = agent.subscribe(lambda event: print(event.type.name, event.data))
await agent.run("hello")
unsub()
```

For named hook registries:

```python
from yom.hooks import HookRegistry

hooks = HookRegistry()

@hooks.on("before_turn")
async def log_turn(state):
    print("turn", state.current_turn)
```

## Plugins

Plugins are reusable packages that contribute capabilities. A plugin can provide
tools, providers, middleware, and setup/teardown behavior.

### Tool plugin

```python
from yom import tool
from yom.plugins import ToolPlugin, YomApp

@tool(name="calculate", description="Perform a calculation")
def calculate(expression: str) -> str:
    return str(eval(expression, {"__builtins__": {}}, {}))

class MathPlugin(ToolPlugin):
    name = "math"
    version = "1.0.0"

    def get_tools(self):
        return [calculate]

app = YomApp()
app.register_plugin(MathPlugin())

agent_tools = ["core", *app.get_tools()]
```

### Middleware plugin

Middleware is exposed by plugins but not automatically applied by the runtime yet.
Applications can retrieve and compose it explicitly.

```python
from yom.plugins import MiddlewarePlugin

class LoggingPlugin(MiddlewarePlugin):
    name = "logging"

    def get_middleware(self):
        return [request_logger]
```

### Provider plugin

```python
from yom.plugins import ProviderPlugin

class MyProviderPlugin(ProviderPlugin):
    name = "my-provider"

    def get_provider(self):
        return MyProvider()
```

### Compatibility

`YomApp` acts as its own plugin manager, so both forms work:

```python
app.register_plugin(plugin)
app.plugin_manager.register_plugin(plugin)
```

## Extensions

`yom.extensions` exists, but it is experimental. Do not rely on it for public
packages yet. Prefer:

- hooks for lifecycle callbacks
- plugins for packaged integrations
- ordinary Python composition for app-specific behavior

The extension API may change before a stable release.
