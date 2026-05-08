# yom Architecture

**Markdown-native agent orchestration runtime.**

yom lets you define AI agents and skills as Markdown files, then spawn specialists on demand from a coordinator agent.

## Core Concept

```
User: "Build me a web scraper"

Coordinator Agent (system prompt)
├── spawn(reviewer, task="Review this code")
├── spawn(coder, task="Write the scraper")
└── spawn(tester, task="Test the scraper")
```

Instead of one agent doing everything poorly, yom lets you:
1. **Define** agents and skills as Markdown files (git-manageable)
2. **Discover** skills on demand via `load_skill` tool
3. **Spawn** sub-agents for specialized tasks
4. **Persist** sessions across interactions

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Agent                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │   Session    │  │    Tools    │  │   SubAgentManager      │ │
│  │  (Backend)   │  │  (Registry) │  │   ┌────────────────┐  │ │
│  └──────────────┘  └──────────────┘  │   │ SubAgentRegistry│  │ │
│                                       │   │  • reviewer.md  │  │ │
│  ┌──────────────┐  ┌──────────────────│   │  • coder.md     │  │ │
│  │    Skills    │  │    Events       │   │  • tester.md    │  │ │
│  │  (on-load)   │  │  (subscribe)    │   └────────────────┘  │ │
│  └──────────────┘  └──────────────────│                       │ │
│                                       │   (spawn_tool)        │ │
│  ┌──────────────┐  ┌──────────────────│                       │ │
│  │   Provider   │  │    Hooks         │                       │ │
│  │ (OpenAI/...)  │  │  (allow/block)  │                       │ │
│  └──────────────┘  └──────────────────┘                       │ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Runtime Settings                            │
│  • system_prompt        • tools                                  │
│  • default_model        • session_backend                        │
│  • provider             • base_url / api_key                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Agent

The main entry point for building AI applications.

```python
from yom import Agent

agent = Agent(
    system_prompt="You are a helpful coordinator. Use spawn_agent when needed.",
    tools=["core", "spawn"],           # spawn_tool is included when spawn enabled
    agents_dir=".yom/agents",          # Load sub-agents from Markdown files
    session_id="user-123",             # Persist conversation
)
```

**Key features:**
- **Event subscription** - Subscribe to agent lifecycle events
- **Cancellation** - Abort running operations
- **Tool calling** - Direct tool invocation
- **Async context manager** - Clean resource management

### 2. Sub-agents

Spawnable specialists defined as Markdown files.

```
.yom/agents/
├── reviewer.md      # Code reviewer
├── coder.md        # General coder
├── tester.md       # Test writer
└── researcher.md   # Web researcher
```

**Example: `.yom/agents/reviewer.md`**
```markdown
---
name: reviewer
description: Reviews code for bugs and issues
mode: subagent
tools: [core]
---

You are a code reviewer. Analyze code carefully for:
- Security vulnerabilities (SQL injection, XSS, etc.)
- Logic errors and edge cases
- Performance issues (N+1 queries, inefficient algorithms)
- Style violations

Provide specific, actionable feedback.
```

**Frontmatter Schema:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Sub-agent identifier |
| `description` | string | Yes | Shown to LLM when deciding to spawn |
| `mode` | string | No | `"subagent"` (spawnable) or `"primary"` (not spawnable) |
| `tools` | list | No | Tools available to this sub-agent |
| `model` | string | No | Override default model |

**Spawning from code:**
```python
@tool
def spawn_agent(ctx: RunContext, agent_type: str, task: str, context: str = "") -> str:
    """Spawn a sub-agent to handle a specialized task."""
    ...

# In practice:
agent = Agent(agents_dir=".yom/agents", tools=["core", "spawn"])
await agent.run("Review /tmp/main.py")  # Coordinator decides to spawn reviewer
```

**Safety limits:**
- `max_depth`: Maximum nesting of sub-agents (default: 4)
- `max_subagent_runs`: Global concurrent sub-agent limit (default: 16)
- `max_children_per_parent`: Children per parent limit (default: 4)
- `default_timeout_seconds`: Default timeout (default: 300s)
- **Prompt injection sanitization**: Blocks common jailbreak attempts

### 3. Skills

Reusable prompt templates discovered on demand.

```
skills/
├── coding/
│   └── SKILL.md
├── research/
│   └── SKILL.md
└── writing/
    └── SKILL.md
```

**Discovery paths (in order):**
1. `~/.yom/skills/` (user skills)
2. `{cwd}/skills/` (project skills)
3. `{cwd}/.yom/skills/` (project skills, alt)
4. Explicit `skill_paths` argument

**Example: `skills/coding/SKILL.md`**
```markdown
---
name: coding
description: Best practices for Python code generation
---

# Coding Skill

When generating code:
1. Follow PEP 8 style guidelines
2. Add type hints to all function signatures
3. Include docstrings for public APIs
4. Write unit tests for new functions
5. Handle errors gracefully

## File Structure
- Keep files under 300 lines
- One class per file (unless tightly coupled)
- Use `__init__.py` for package exports
```

**Loading via tool:**
```python
# Agent sees this in system prompt:
# "Available skills: coding, research, writing"
# Call load_skill(name="coding") to load full skill content

@tool
def load_skill(ctx: RunContext, name: str) -> str:
    """Load a skill's full instructions into context."""
    ...

# In agent behavior:
# 1. LLM sees skill catalog in system prompt
# 2. LLM calls load_skill(name="coding") when coding task starts
# 3. Full skill content appended to system prompt
# 4. LLM follows skill's specific guidelines
```

### 4. Sessions

Conversation memory with pluggable backends.

```python
# In-memory (default)
agent = Agent(session_id="user-123")

# File-based (persists to disk)
agent = Agent(
    session_id="user-123",
    session_backend="file",
    session_dir="./sessions"
)

# Load or create state
state = await runtime._settings.session_backend.load(session_id)
if state is None:
    state = AgentState.create(runtime_id="agent", system_prompt="...")
```

**State structure:**
```python
class AgentState:
    runtime_id: str
    session_id: str
    system_prompt: str
    messages: list[Message]
    current_turn: int
    metadata: dict[str, Any]
    loaded_skills: list[str]
```

### 5. Tools

Type-safe tool definitions with Pydantic validation.

```python
from pydantic import BaseModel, Field
from yom import Agent, tool, RunContext

# Basic tool
@tool
def get_weather(location: str, units: str = "celsius") -> str:
    """Get weather for a location."""
    return f"Weather in {location}: sunny, 22°{units}"

# Pydantic input model
class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=10, description="Max results")

@tool(input_model=SearchInput)
def search(input: SearchInput) -> str:
    return f"Found {input.limit} results for '{input.query}'"

# Dependency injection
@dataclass
class MyDeps:
    api_key: str
    db: Database

@tool
def query_db(ctx: RunContext[MyDeps], sql: str) -> str:
    return f"Result from {ctx.deps.db}: ..."

agent = Agent(tools=["core", get_weather, search, query_db])
```

### 6. Providers

Multi-provider LLM support.

```python
from yom import Agent
from yom.providers import OpenAICompatibleProvider, AnthropicCompatibleProvider

# Default (checks MINIMAX_API_KEY, then OPENAI_API_KEY)
agent = Agent()

# Explicit provider
agent = Agent(provider="anthropic")
agent = Agent(provider="google")
agent = Agent(provider="ollama", base_url="http://localhost:11434")
```

### 7. Events

Subscribe to agent lifecycle for monitoring/audit.

```python
from yom import Agent, AgentEvent, AgentEventType

agent = Agent(tools=["core"])

# Subscribe
unsub = agent.subscribe(lambda event: print(f"Event: {event.type.name}"))

# Async handler (returns Task)
async def save_event(event: AgentEvent):
    await db.save(event)

unsub = agent.subscribe(save_event)

# Events:
# - AGENT_START, AGENT_END
# - TURN_START, TURN_END
# - TOOL_START, TOOL_END
# - MESSAGE_DELTA
# - ERROR

# Unsubscribe
unsub()
```

### 8. Hooks

Control tool execution before/after.

```python
from yom import global_hooks, allow, block

# Allow specific tool
global_hooks.register("read", allow)

# Block dangerous tool
global_hooks.register("shell", block(reason="Shell disabled for safety"))

# Custom hook
def audit_shell(ctx, tool_name, args):
    audit_log.write(f"{tool_name} called with {args}")
    return allow()

global_hooks.register("shell", audit_shell)
```

### 9. Plugins

Hot-reloadable extensions.

```python
from yom.plugins import YomApp, ToolPlugin

app = YomApp()
app.plugin_manager.load_plugins("./plugins")

# Or create plugin
class MyPlugin(ToolPlugin):
    name = "my-plugin"
    
    @tool
    def my_tool(self):
        return "Hello from plugin!"

app.plugin_manager.register_plugin(MyPlugin())
```

---

## Directory Structure

```
project/
├── .yom/
│   └── agents/           # Sub-agent definitions (Markdown)
├── skills/              # Skill definitions (Markdown)
│   ├── coding/
│   │   └── SKILL.md
│   └── research/
│       └── SKILL.md
├── sessions/            # Session persistence (optional)
│   ├── user-123.json
│   └── user-456.json
├── agents.py            # Your agent code
└── pyproject.toml
```

---

## Comparison with Alternatives

| Feature | yom | Pydantic AI | LangGraph |
|---------|-----|------------|----------|
| **Multi-agent** | Sub-agents (spawnable) | ❌ | ✅ (graph-based) |
| **Skill system** | Markdown-based | ❌ | ❌ |
| **Session persistence** | ✅ File/memory | ❌ | ✅ |
| **Type safety** | ✅ Pydantic | ✅ (core) | ❌ |
| **Authoring** | Markdown files | Code only | Code only |
| **Complexity** | Low | Low | High |
| **Deployment** | RPC, FastAPI, Telegram | Manual | Manual |

---

## Design Principles

### 1. Markdown-Native
Agents and skills are Markdown files you can:
- Git-manage (version, diff, review)
- Share via npm/pip packages
- Edit without redeploying

### 2. Lazy Loading
- Sub-agent prompts loaded only when spawned
- Skills loaded only when requested
- No bloat for unused features

### 3. Safety First
- Prompt injection sanitization
- Depth/count/timeout limits
- Hooks for auditing

### 4. Type-Safe Tools
Pydantic validation for:
- Tool inputs
- Tool outputs  
- Agent responses

### 5. Observable
- Event subscription for all lifecycle hooks
- Structured logging
- Debug mode with traces

---

## Extension Points

### Custom Toolset
```python
from yom.toolsets import http_request, shell

agent = Agent(tools=["core", http_request, shell])
```

### Custom Provider
```python
from yom.providers import BaseProvider

class CustomProvider(BaseProvider):
    def complete(self, messages, model, config):
        # Your implementation
        ...

agent = Agent(provider=CustomProvider())
```

### Custom Session Backend
```python
from yom.session import SessionBackend

class RedisBackend(SessionBackend):
    async def load(self, session_id: str) -> AgentState:
        return await redis.get(session_id)
    
    async def save(self, session_id: str, state: AgentState):
        await redis.set(session_id, state)

agent = Agent(session_backend=RedisBackend())
```

---

## Security

### Prompt Injection Prevention
Blocks patterns like:
- "ignore all previous instructions"
- "you are now..."
- "new system prompt:"

Context from parent agent is sanitized before passing to sub-agent.

### Tool Hooks
Control which tools can be called and add auditing.

### Session Isolation
Each session has isolated state; sub-agents track parent-child relationships.

---

## Future Considerations

- **Skill marketplace**: Share skills via package registry
- **Agent collaboration**: Sub-agents that communicate directly
- **Distributed sessions**: Redis-backed session sharing
- **Streaming sub-agents**: Real-time output from spawned agents
