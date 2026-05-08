# yom Quick Start

**Build multi-agent applications with Markdown-defined agents and skills.**

## Installation

```bash
pip install yom
```

## Your First Agent

```python
from yom import Agent

agent = Agent(tools=["core"])
result = await agent.run("What is Python?")
print(result)
```

## Spawn Sub-agents

### 1. Create agent definitions as Markdown files

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

**`.yom/agents/coder.md`**
```markdown
---
name: coder
description: Writes clean, tested code
mode: subagent
tools: [core]
---

You are a Python coder. Write:
- Type-annotated functions
- Docstrings for public APIs
- Unit tests with pytest
```

### 2. Use them from your agent

```python
from yom import Agent

# Coordinator agent with access to sub-agents
agent = Agent(
    tools=["core", "spawn"],  # "spawn" enables sub-agent spawning
    agents_dir=".yom/agents",
    system_prompt="""You are a helpful coordinator.
    
    When asked to write code, spawn a coder agent.
    When asked to review code, spawn a reviewer agent.
    
    Use spawn_agent to dispatch to specialists.
    """
)

# The coordinator will spawn reviewer for this
result = await agent.run("Review /tmp/app.py")
```

## Load Skills On Demand

### 1. Create skill files

```bash
mkdir -p skills/coding
```

**`skills/coding/SKILL.md`**
```markdown
---
name: coding
description: Best practices for Python code generation
---

# Coding Skill

When generating Python code:
1. Follow PEP 8 style guidelines
2. Add type hints to all functions
3. Include docstrings for public APIs
4. Write pytest unit tests

## Template
```python
def function_name(param: Type) -> ReturnType:
    """Describe what this does.
    
    Args:
        param: What this parameter is
        
    Returns:
        What this returns
    """
    pass
```
```

### 2. Skills auto-discovered

Skills are discovered from:
- `~/.yom/skills/`
- `{cwd}/skills/`
- `{cwd}/.yom/skills/`

The agent sees available skills in its system prompt and can call `load_skill(name="coding")` to load full skill content.

## Persistent Sessions

```python
from yom import Agent

# Sessions persist across restarts
agent = Agent(session_id="user-alice")

await agent.run("My name is Alice")
# Later...
await agent.run("What is my name?")  # "Your name is Alice"
```

### Session backends

```python
# Memory (default)
agent = Agent(session_id="user-123")

# File-based (persists to disk)
agent = Agent(
    session_id="user-123",
    session_backend="file",
    session_dir="./sessions"
)
```

## Type-Safe Tools

```python
from pydantic import BaseModel, Field
from yom import Agent, tool, RunContext

# Pydantic input validation
class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Max results")

@tool(input_model=SearchInput)
def search(input: SearchInput) -> str:
    return f"Found {input.limit} results for '{input.query}'"

# Dependency injection
@dataclass
class MyDeps:
    db: Database

@tool  
def query(ctx: RunContext[MyDeps], sql: str) -> str:
    return f"Result: {ctx.deps.db.query(sql)}"

agent = Agent(tools=["core", search, query])
```

## Event Subscription

```python
from yom import Agent, AgentEvent

agent = Agent(tools=["core"])

# Subscribe to events
def log_event(event):
    print(f"[{event.type.name}] {event.data}")

unsub = agent.subscribe(log_event)

await agent.run("Hello")

unsub()  # Unsubscribe
```

## Deployment

### Telegram Bot

```python
from yom import Agent
# Telegram integration not included in core package

agent = Agent(tools=["core", "spawn"], agents_dir=".yom/agents")
# Build your own bot adapter around agent.run(...)

await bot.poll()
```

### FastAPI

```python
from yom import Agent, create_agent_router

agent = Agent(tools=["core"])
router = create_agent_router(agent)

# In your FastAPI app
app.include_router(router)
```

### RPC Server

```python
from yom import Agent

agent = Agent(tools=["core"])

# Serve agent via RPC
# Expose via your framework (e.g., FastAPI)

# Client can connect
client = create_rpc_client("http://localhost:8080")
result = await client.run("Hello")
```

## CLI

```bash
# Run a prompt
yom run "What is 2+2?"

# Interactive REPL
yom repl

# Run with config
yom run --config config.yaml
```

## Example: Complete Multi-Agent Setup

```
project/
├── .yom/
│   └── agents/
│       ├── reviewer.md
│       └── coder.md
├── skills/
│   └── coding/
│       └── SKILL.md
└── agent.py
```

**`agent.py`**
```python
from yom import Agent

agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
    system_prompt="""You coordinate a team of specialists.
    
    Available sub-agents:
    - reviewer: Code review
    - coder: Code generation
    
    Use spawn_agent to dispatch tasks appropriately.
    """
)

async def main():
    result = await agent.run("Write and review a JSON parser in Python")
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Next Steps

- [Architecture](architecture.md) - Deep dive into yom's design
- [Examples](../examples/) - More usage examples
- [API Reference](../yom/) - Full API documentation
