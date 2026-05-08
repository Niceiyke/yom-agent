# yom - Markdown-Native Agent Orchestration

**yom** is an agent runtime for building multi-agent applications. Define agents and skills as Markdown files, spawn specialists on demand.

```python
from yom import Agent

agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
    system_prompt="You are a helpful coordinator. Spawn specialists when needed."
)

result = await agent.run("Review /tmp/code.py")  # Spawns reviewer sub-agent
```

## Core Features

| Feature | Description |
|---------|-------------|
| **Sub-agents** | Spawn specialists from Markdown definitions |
| **Skills** | Loadable prompt templates discovered on demand |
| **Sessions** | Persistent conversation memory |
| **Type-safe tools** | Pydantic validation for inputs and outputs |
| **Multi-provider** | OpenAI, Anthropic, Google, Ollama |
| **Event subscription** | Monitor agent lifecycle |
| **Plugins** | Hot-reloadable extensions |

## Installation

```bash
pip install yom
```

With extras:
```bash
pip install yom[anthropic,google,s3,telegram]
```

## Quick Start

### 1. Create sub-agents as Markdown files

```bash
mkdir -p .yom/agents
```

**`.yom/agents/reviewer.md`**
```markdown
---
name: reviewer
description: Reviews code for bugs and issues
mode: subagent
tools: [core]
---

You are a code reviewer. Analyze code for:
- Security vulnerabilities
- Logic errors
- Performance issues

Provide specific, actionable feedback.
```

### 2. Use them from your agent

```python
from yom import Agent

agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
)

# The coordinator spawns reviewer for this
result = await agent.run("Review /tmp/app.py")
```

## Key Concepts

### Sub-agents

Spawnable specialists defined as Markdown files. The coordinator agent decides when to spawn based on task requirements.

```
.yom/agents/
├── reviewer.md      # Code reviewer
├── coder.md        # General coder
└── tester.md       # Test writer
```

**Frontmatter schema:**
```yaml
name: reviewer                    # Required: agent identifier
description: Reviews code...      # Required: shown to LLM for routing
mode: subagent                    # "subagent" (spawnable) or "primary"
tools: [core]                     # Tools available to this agent
model: gpt-4                      # Optional: override default model
```

### Skills

Reusable prompt templates loaded on demand.

```
skills/
├── coding/
│   └── SKILL.md
└── research/
    └── SKILL.md
```

Discovery paths: `~/.yom/skills/`, `{cwd}/skills/`, `{cwd}/.yom/skills/`

### Sessions

Persistent conversation memory.

```python
agent = Agent(session_id="user-123")

await agent.run("My name is Alice")
await agent.run("What is my name?")  # "Your name is Alice"
```

### Type-Safe Tools

```python
from pydantic import BaseModel, Field
from yom import Agent, tool

class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Max results")

@tool(input_model=SearchInput)
def search(input: SearchInput) -> str:
    return f"Found {input.limit} results"

agent = Agent(tools=["core", search])
```

## Deployment

### Telegram Bot

```python
from yom import Agent
from yom.toolsets.telegram import TelegramBot

agent = Agent(tools=["core", "spawn"], agents_dir=".yom/agents")
bot = TelegramBot(token="TOKEN", agent=agent)
await bot.poll()
```

### FastAPI

```python
from yom import create_agent_router

router = create_agent_router(agent)
app.include_router(router)
```

### RPC Server

```python
from yom import serve_rpc

await serve_rpc(agent, host="0.0.0.0", port=8080)
```

## CLI

```bash
yom run "What is 2+2?"        # Run a prompt
yom repl                        # Interactive REPL
yom run --config config.yaml   # Run with config
```

## Directory Structure

```
project/
├── .yom/
│   └── agents/           # Sub-agent definitions
├── skills/               # Skill definitions
│   └── coding/
│       └── SKILL.md
└── agent.py              # Your agent code
```

## Comparison

| Feature | yom | Pydantic AI | LangGraph |
|---------|-----|------------|-----------|
| Multi-agent | ✅ Sub-agents | ❌ | ✅ Graph |
| Skills | ✅ Markdown | ❌ | ❌ |
| Sessions | ✅ File/memory | ❌ | ✅ |
| Authoring | Markdown files | Code only | Code only |

## Examples

See `examples/` for complete examples:
- `customer_support.py` - Real-world agent with output validation
- `pydantic_validation.py` - Pydantic tool patterns
- `telegram/` - Telegram bot integration

## Documentation

- [Quick Start](docs/quickstart.md) - Get up and running
- [Architecture](docs/architecture.md) - Deep dive into design

## License

MIT
