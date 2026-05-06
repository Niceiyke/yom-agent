# yom - Agent Runtime Framework

**yom** is an open-source agent runtime that makes it easy to build AI-powered applications with tool calling, session management, and multi-provider support.

```python
from yom import Agent

agent = Agent(tools=["core"])
result = await agent.run("Hello, world!")
```

## Features

- 🔧 **Tool Calling** - Extend agents with custom tools
- 💾 **Sessions** - Conversation memory that persists
- 🔌 **Plugins** - Hot-reloadable extensions
- 🌐 **Multi-Provider** - OpenAI, Anthropic, Google, Ollama, NVIDIA
- 🧪 **Testing** - Built-in testing utilities
- 🐛 **Debug Mode** - Trace and debug agent behavior

## Installation

```bash
pip install yom
```

With extras:
```bash
pip install yom[anthropic,google,s3,telegram]
```

## Quick Start

```python
from yom import Agent

agent = Agent(
    tools=["core"],
    system_prompt="You are a helpful assistant."
)

# Run synchronously
result = agent.run_sync("What is Python?")

# Or async
import asyncio
result = asyncio.run(agent.run("What is Python?"))
```

## Tools

### Built-in Tools

```python
from yom import Agent

# Use built-in tools by name
agent = Agent(tools=["core", "http_request", "shell"])

# Your tools
from yom import tool

@tool(name="my_tool", description="Does something")
def my_tool(arg1: str) -> str:
    return f"Hello, {arg1}!"

agent = Agent(tools=["core", my_tool])
```

### Available Tool Categories

| Category | Tools |
|----------|-------|
| **core** | read, write, edit, bash, glob, grep |
| **http** | http_request, get_json |
| **database** | query_db, db_schema |
| **github** | github_api, github_read_file, github_search |
| **storage** | s3_put, s3_get, s3_list |
| **shell** | shell, shell_script |

## Providers

yom supports multiple LLM providers:

```python
from yom import Agent

# OpenAI (default)
agent = Agent()  # Uses OPENAI_API_KEY env var

# MiniMax
agent = Agent(provider="minimax")  # Uses MINIMAX_API_KEY

# Anthropic
from yom.providers import AnthropicProvider
agent = Agent(provider=AnthropicProvider(api_key="sk-..."))

# Ollama (local)
from yom.providers import OllamaProvider
agent = Agent(provider=OllamaProvider(model="llama3"))
```

## Sessions

Agents remember conversations:

```python
agent = Agent(session_id="user-123")

# First interaction
agent.run("My name is Alice")
# → Remembers "Alice"

# Later
agent.run("What is my name?")
# → "Your name is Alice"
```

### Session Backends

```python
# In-memory (default)
agent = Agent(session_id="123")

# File-based (persists to disk)
agent = Agent(
    session_id="123",
    session_backend="file",
    session_dir="./sessions"
)

# Or explicit
from yom.session import FileSessionBackend
agent = Agent(
    session_id="123",
    session_backend=FileSessionBackend(dir="./sessions")
)
```

## Testing

```python
from yom.testing import fake_agent, MockProvider

# Fake agent for testing
agent = fake_agent("I am a test agent")
result = agent.run_sync("Hello")
assert "test agent" in result

# Mock provider
provider = MockProvider(responses=["First", "Second", "Third"])
agent = fake_agent(provider=provider)
```

## Debug Mode

```python
from yom.debug import enable_debug, trace, get_recorder

# Enable debug output
enable_debug()

# Trace execution
with trace("my_operation") as ctx:
    # ... do stuff
    pass

# View recorded traces
recorder = get_recorder()
for event in recorder.events:
    print(event)
```

## Plugin System

```python
from yom.plugins import YomApp, ToolPlugin

app = YomApp()

# Load plugins from directory
app.plugin_manager.load_plugins("./plugins")

# Create plugin
class MyPlugin(ToolPlugin):
    name = "my-plugin"
    
    @staticmethod
    @tool(name="my_tool")
    def my_tool():
        return "Hello from plugin!"
    
    def get_tools(self):
        return [self.my_tool]

app.plugin_manager.register_plugin(MyPlugin())
```

## Telegram Bot

```python
from yom import Agent
from yom.toolsets.telegram import TelegramBot

agent = Agent(tools=["core"])
bot = TelegramBot(token="YOUR_BOT_TOKEN", agent=agent)

# Run polling
await bot.poll()
```

### Telegram Commands

```
/start       - Welcome
/new <name>  - Create session
/switch <name> - Switch session
/sessions    - List sessions
/reset       - Clear history
/help        - Show help
```

## CLI

```bash
# Run a prompt
yom run "What is 2+2?"

# Interactive REPL
yom repl

# Run with config
yom run --config config.yaml

# Telegram bot
yom telegram polling --token "TOKEN"
```

## API Reference

### Agent

```python
from yom import Agent

agent = Agent(
    system_prompt="You are...",      # System prompt
    tools=["core", my_tool],         # Tools to use
    model="gpt-4",                   # Model name
    session_id="user-123",           # Session ID
    session_backend="file",          # Session backend
    session_dir="./sessions",        # Session directory
)
```

### Tools

```python
from yom import tool

@tool(
    name="my_tool",
    description="Does something",
    schema={
        "type": "object",
        "properties": {
            "arg1": {"type": "string"}
        },
        "required": ["arg1"]
    }
)
def my_tool(arg1: str) -> str:
    """Tool description."""
    return f"Result: {arg1}"
```

## Configuration

### YAML Config

```yaml
# config.yaml
runtime_id: my-agent
system_prompt: You are a helpful assistant.

provider:
  name: openai
  model: gpt-4o-mini

tools:
  - core
  - http_request

session:
  backend: file
  dir: ./sessions
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `MINIMAX_API_KEY` | MiniMax API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GOOGLE_API_KEY` | Google API key |
| `YOM_DEBUG` | Enable debug mode (1/0) |

## Examples

See `examples/` directory for complete examples:

- `simple.py` - Basic usage
- `with_tools.py` - Custom tools
- `telegram_bot.py` - Telegram integration
- `sessions.py` - Session management

## License

MIT License
