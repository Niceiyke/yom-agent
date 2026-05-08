# Sub-agents

**Spawnable specialists defined as Markdown files.**

Sub-agents let you build multi-agent systems where a coordinator spawns specialists on demand.

## Overview

```
User: "Build me a web scraper"

Coordinator Agent
├── spawn(reviewer, task="Review this scraper")
├── spawn(coder, task="Write the scraper")
└── spawn(tester, task="Test the scraper")
```

vs. single agent doing everything poorly.

## How It Works

1. **Define** agents as Markdown files in `.yom/agents/`
2. **Load** them via `agents_dir` parameter
3. **Spawn** via `spawn_agent` tool (included with `"spawn"`)

```python
from yom import Agent

agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
)
```

The coordinator agent sees available sub-agents in its context and decides when to spawn.

## Creating Sub-agents

### Directory Structure

```
.yom/agents/
├── reviewer.md
├── coder.md
└── tester.md
```

### Markdown Format

```markdown
---
name: reviewer
description: Reviews code for bugs and issues
mode: subagent
tools: [core]
model: gpt-4
---

You are a code reviewer. Analyze code for:
- Security vulnerabilities
- Logic errors
- Performance issues

Provide specific, actionable feedback.
```

### Frontmatter Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Sub-agent identifier (must match filename) |
| `description` | string | Yes | Shown to LLM for routing decisions |
| `mode` | string | No | `"subagent"` (spawnable) or `"primary"` (not spawnable) |
| `tools` | list | No | Tools available to this sub-agent |
| `model` | string | No | Override default model |

### Prompt Body

Everything after the closing `---` is the agent's system prompt. This is lazy-loaded when the sub-agent spawns.

## Spawning

### Automatic (via coordinator)

The coordinator LLM decides when to spawn based on available sub-agents:

```python
agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
    system_prompt="""You coordinate a team of specialists.
    
    Use spawn_agent to dispatch tasks to:
    - reviewer: Code review
    - coder: Code generation
    - tester: Test writing
    """
)

result = await agent.run("Write and review a JSON parser")
# Coordinator may spawn coder then reviewer
```

### Manual Registration

```python
from yom import Agent
from yom.subagent import SubAgentDefinition

agent = Agent(tools=["core", "spawn"])

agent.register_subagent(
    name="researcher",
    description="Researches topics on the web",
    system_prompt="You are a researcher. Search the web for...",
    tools=["core", "http_request"],
)
```

### From Code

```python
@tool
def spawn_my_agent(ctx: RunContext, task: str) -> str:
    """Spawn a custom agent."""
    from yom.subagent import SubAgentManager
    
    manager = get_default_manager()
    result = await manager.run(
        SubAgentRequest(
            agent_type="reviewer",
            task=task,
            context=ctx.deps.context,
        )
    )
    return result.summary
```

## Safety

Sub-agents have built-in safety limits:

| Limit | Default | Description |
|-------|---------|-------------|
| `max_depth` | 4 | Maximum nesting of sub-agents |
| `max_subagent_runs` | 16 | Global concurrent runs |
| `max_children_per_parent` | 4 | Children per parent agent |
| `default_timeout_seconds` | 300 | Default timeout (5 min) |

### Prompt Injection Prevention

Context passed to sub-agents is sanitized to block common jailbreak patterns:

```python
PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard previous instructions", 
    "you are now...",
    "new system prompt:",
    "override instructions",
]
```

If suspicious content is detected, it gets replaced with `[redacted due to potential prompt injection]`.

### Timeout Handling

```python
result = await manager.run(
    SubAgentRequest(
        agent_type="slow_agent",
        task="Do something slow",
        timeout_seconds=60,  # Override default
    )
)

if result.status == "timeout":
    print(f"Timed out after {result.finished_at - result.started_at}s")
```

## Results

```python
@dataclass
class SubAgentResult:
    child_id: str           # Unique child identifier
    agent_type: str        # Which agent was spawned
    status: str            # "succeeded", "failed", "timeout", "cancelled"
    summary: str           # Agent's final response (truncated at 4000 chars)
    error: str | None      # Error message if failed
    started_at: float     # Unix timestamp
    finished_at: float    # Unix timestamp
    token_usage: dict     # If provider supports it
```

## Example: Code Review Pipeline

### 1. Create agents

**`.yom/agents/reviewer.md`**
```markdown
---
name: reviewer
description: Reviews code for bugs and security issues
mode: subagent
tools: [core]
---

You are a code reviewer. Check for:
- Security: SQL injection, XSS, auth bypass
- Correctness: Logic errors, edge cases
- Performance: N+1, memory leaks

Be specific. Provide file:line and suggestion.
```

**`.yom/agents/coder.md`**
```markdown
---
name: coder
description: Writes clean Python code
mode: subagent
tools: [core]
---

You are a Python coder. Write:
- Type hints on all functions
- Docstrings on public APIs
- pytest tests

Follow PEP 8. Max 300 lines per file.
```

### 2. Use them

```python
from yom import Agent

agent = Agent(
    tools=["core", "spawn"],
    agents_dir=".yom/agents",
    system_prompt="""You coordinate a code review pipeline.
    
    When asked to write code:
    1. Spawn coder to generate the code
    2. Spawn reviewer to review it
    3. Summarize findings for the user
    """,
)

async def main():
    result = await agent.run("Write a JSON parser and review it")
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Tips

### Keep Prompts Focused
Sub-agent prompts should be narrow. The coordinator decides *when* to spawn; the sub-agent handles *how* to execute.

### Use Context Wisely
```python
# Good - coordinator passes relevant context
result = await manager.run(
    SubAgentRequest(
        agent_type="reviewer",
        task="Review this function",
        context="Function to review:\ndef parse_json(text): ...",
    )
)

# Bad - no context, sub-agent blind
result = await manager.run(
    SubAgentRequest(
        agent_type="reviewer",
        task="Review something",  # Vague task
    )
)
```

### Limit Depth
Each level of nesting adds latency and cost. `max_depth=4` is usually enough.

### Share Tools, Not Prompts
Don't embed shared instructions in every sub-agent. Use the Skills system instead.
