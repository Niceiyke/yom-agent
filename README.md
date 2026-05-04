# yom-agent

Configurable, installable agent runtime with tool calling, session management, and multi-provider LLM support.

## Installation

```bash
pip install yom-agent
```

Or from source:
```bash
cd packages/yom-agent
pip install -e .
```

## Quick Start

```python
from yom import Agent

agent = Agent(
    system_prompt="You are a helpful coding assistant",
    tools=["core"]  # read, write, edit, bash, grep, glob
)

result = agent.run_sync("Read /tmp/test.py and explain it")
print(result)
```

## Core Concepts

### Agent

The `Agent` class is the main entry point:

```python
from yom import Agent

agent = Agent(
    system_prompt="You are helpful",
    tools=["core", "spawn"],  # "core" includes built-in tools, "spawn" enables sub-agents
    runtime_id="my-agent",
    session_id="user-123",     # Optional: enables session persistence
)
```

### Tools

#### Built-in Tools (`core`)

| Tool | Description |
|------|-------------|
| `read` | Read file contents |
| `write` | Write content to file |
| `edit` | Replace old_string with new_string in file |
| `bash` | Execute bash command |
| `cmd` | Execute Windows command |
| `grep` | Search for regex pattern in files |
| `glob` | Find files matching glob pattern |

#### Custom Tools

```python
from yom import Agent, tool

agent = Agent(tools=[])

@tool(name="weather", description="Get weather for a location")
def get_weather(location: str) -> str:
    return f"Weather in {location}: sunny"

agent.add_tool(get_weather)
```

Or with explicit schema:

```python
@tool(schema={
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"}
    },
    "required": ["query"]
})
def search(query: str) -> str:
    return f"Results for: {query}"
```

### Sessions

Sessions maintain conversation history:

```python
# File-based sessions (persisted to disk)
agent = Agent(session_backend="file", session_dir="./data")

# In-memory sessions (ephemeral)
agent = Agent(session_backend="memory")

# Later, resume the same session
result = await agent.run("What was I asking about?")
```

### Sub-agents

Spawn specialized agents for specific tasks:

```python
# Register a sub-agent
agent = Agent(tools=["core", "spawn"])
agent.register_subagent(
    name="reviewer",
    description="Reviews code for bugs",
    system_prompt="You are a code reviewer. Analyze code carefully...",
    tools=["core"]
)

# Or load from markdown files in a directory
agent = Agent(agents_dir=".yom/agents")
# Creates .yom/agents/*.md files with frontmatter defining agents
```

### Context Management

Control context window usage:

```python
from yom import RuntimeSettings, build_runtime
from yom.context import ContextConfig, TruncationStrategy

settings = RuntimeSettings(
    runtime_id="my-agent",
    max_context_tokens=100000,  # Truncate when context exceeds this
    context_config=ContextConfig(
        max_tokens=100000,
        strategy=TruncationStrategy.TRUNCATE,
        preserve_last_n_messages=2,  # Always keep last 2 messages
    )
)

runtime = build_runtime(settings)
```

### Hooks

Monitor agent events:

```python
from yom import HookRegistry

hooks = HookRegistry()

@hooks.before_turn
async def on_before_turn(state, iteration):
    print(f"Turn {iteration} starting")

@hooks.after_turn
async def on_after_turn(state, iteration, response):
    print(f"Turn {iteration} completed")

@hooks.on_tool_call
async def on_tool(state, call):
    print(f"Tool called: {call.name}")

# Pass hooks to runtime via RuntimeDeps
runtime = build_runtime(settings, deps=RuntimeDeps(hooks=hooks))
```

Available hooks: `agent_start`, `agent_end`, `turn_start`, `turn_end`, `before_turn`, `after_turn`, `before_tool_call`, `after_tool_call`, `on_tool_call`, `on_tool_result`, `session_start`, `session_end`, `on_error`.

### Providers

yom supports multiple LLM providers:

```python
from yom import create_provider

# Auto-detect from model name
provider = create_provider(model="claude-3-5-sonnet-latest")

# Explicit
provider = create_provider(provider="openai", api_key="sk-...")
```

Supported providers: OpenAI (and OpenAI-compatible like MiniMax), Anthropic, Google.

## Runtime Configuration

### RuntimeSettings

```python
from yom import RuntimeSettings

settings = RuntimeSettings(
    runtime_id="my-agent",
    system_prompt="You are helpful",
    default_model="MiniMax-M2.7",  # Provider auto-detected
    max_turns=50,                  # Max turns per run
    max_context_tokens=128000,     # Context window limit
    log_level="INFO",               # Logging level
    timeout=120.0,                 # Request timeout
)
```

### Building Runtimes

```python
from yom import build_runtime, build_runtime_from_yaml

# From settings
runtime = build_runtime(settings)

# From YAML file
runtime = build_runtime_from_yaml("config.yaml")

# From environment variables (AGENT_* prefix)
runtime = build_runtime_from_env()
```

### Example YAML Config

```yaml
runtime_id: my-agent
system_prompt: You are a helpful coding assistant
default_model: MiniMax-M2.7
max_turns: 50
max_context_tokens: 128000
session:
  backend: file
  path: ./sessions
tools:
  - core
log_level: INFO
```

## FastAPI Integration

```python
from yom.fastapi import create_agent_app
from yom import RuntimeSettings

app = create_agent_app(
    settings=RuntimeSettings(
        runtime_id="helpdesk",
        system_prompt="You are a helpful helpdesk agent",
    ),
    prefix="/agent"
)

# Run with: uvicorn.run(app, host="0.0.0.0", port=8000)
```

Endpoints:
- `GET /agent/health` - Health check
- `GET /agent/tools` - List available tools
- `POST /agent/{session_id}/start` - Run prompt
- `GET /agent/{session_id}/history` - Get session history
- `WS /agent/{session_id}/ws` - WebSocket for streaming

## Security

### Path Validation

File operations are restricted to allowed directories (`~` by default):

```python
# Protected paths are blocked automatically
# /etc, /sys, /proc are always protected
```

### Command Allowlisting

For bash tool, restrict allowed commands:

```python
from yom.tools.core import set_allowed_commands

# Only allow safe read-only commands
set_allowed_commands(["ls", "cat", "grep", "find", "head", "tail"])
```

### Timeout Limits

Bash commands have a max timeout of 120 seconds.

## Logging

```python
from yom.logging_config import setup_logging, get_logger

# Configure logging
setup_logging(level="DEBUG")

# Use in modules
logger = get_logger("my_module")
logger.info("message", key="value")
```

Log level can also be set via `RuntimeSettings(log_level="DEBUG")`.

## API Reference

### yom.Agent

- `run(prompt: str) -> str` - Async run
- `run_sync(prompt: str) -> str` - Sync run
- `clear_session()` - Clear current session
- `register_subagent(...)` - Register a sub-agent
- `list_subagents() -> list[str]` - List available sub-agents
- `available_tools -> list[str]` - Get tool names

### yom.RuntimeSettings

Configuration for runtime creation. See Configuration section above.

### yom.ContextManager

- `truncate_messages(messages: list[dict], max_tokens: int) -> list[dict]`
- `count_tokens(text: str) -> int`
- `get_stats(messages: list[dict]) -> ContextStats`

## License

MIT