# yom Cookbook

Common recipes and patterns for building AI agents with yom.

## Table of Contents

1. [Basic Usage](#basic-usage)
2. [Tool Creation](#tool-creation)
3. [Session Management](#session-management)
4. [Custom Providers](#custom-providers)
5. [Testing](#testing)
6. [Debugging](#debugging)
7. [Telegram Bot](#telegram-bot)
8. [Web Scraping](#web-scraping)
9. [Database Operations](#database-operations)
10. [File Operations](#file-operations)

---

## Basic Usage

### Simple Agent

```python
from yom import Agent

agent = Agent(system_prompt="You are a helpful assistant.")
result = agent.run_sync("Hello!")
print(result)
```

### Async Agent

```python
import asyncio
from yom import Agent

async def main():
    agent = Agent(tools=["core"])
    result = await agent.run("What's the weather?")
    print(result)

asyncio.run(main())
```

### With Tools

```python
from yom import Agent, tool

@tool(name="greet", description="Greet a user")
def greet(name: str) -> str:
    return f"Hello, {name}!"

agent = Agent(tools=["core", greet])
result = agent.run_sync("Greet Alice")
# Output: "Hello, Alice!"
```

---

## Tool Creation

### Simple Tool

```python
from yom import tool

@tool(name="hello", description="Say hello")
def hello() -> str:
    return "Hello, World!"
```

### Tool with Parameters

```python
@tool(
    name="calculate",
    description="Perform a calculation",
    schema={
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
            "operation": {"type": "string", "enum": ["add", "subtract", "multiply"]}
        },
        "required": ["a", "b", "operation"]
    }
)
def calculate(a: float, b: float, operation: str) -> str:
    if operation == "add":
        return str(a + b)
    elif operation == "subtract":
        return str(a - b)
    elif operation == "multiply":
        return str(a * b)
    return "Unknown operation"
```

### Async Tool

```python
import asyncio
from yom import tool

@tool(name="fetch_url", description="Fetch content from URL")
async def fetch_url(url: str) -> str:
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

### Tool with Error Handling

```python
@tool(name="read_file", description="Read a file")
def read_file(path: str) -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error: {str(e)}"
```

---

## Session Management

### User Sessions

```python
from yom import Agent

# Each user gets their own session
user1_agent = Agent(session_id="user-1")
user2_agent = Agent(session_id="user-2")

user1_agent.run("My name is Alice")
user2_agent.run("My name is Bob")

# Later - each remembers their own name
print(user1_agent.run_sync("What is my name?"))  # "Your name is Alice"
print(user2_agent.run_sync("What is my name?"))  # "Your name is Bob"
```

### Persistent Sessions

```python
from yom import Agent

agent = Agent(
    session_id="alice",
    session_backend="file",  # Persists to disk
    session_dir="./sessions"
)

# Session survives restarts
agent.run("My favorite color is blue")

# Later...
agent.run("What is my favorite color?")  # "Blue"
```

### Session with TTL

```python
from yom import Agent
from yom.session import FileSessionBackend

backend = FileSessionBackend(
    dir="./sessions",
    ttl=3600  # 1 hour
)

agent = Agent(session_id="temp-user", session_backend=backend)
```

---

## Custom Providers

### OpenAI

```python
from yom import Agent

agent = Agent(model="gpt-4o")
```

### Anthropic

```python
from yom.providers import AnthropicProvider
from yom import Agent

provider = AnthropicProvider(api_key="sk-ant-...")
agent = Agent(provider=provider, model="claude-3-5-sonnet")
```

### Ollama (Local)

```python
from yom.providers import OpenAICompatibleProvider
from yom import Agent

provider = OpenAICompatibleProvider(
    base_url="http://localhost:11434/v1",
)
agent = Agent(provider="openai", base_url="http://localhost:11434/v1", model="llama3")
```

### NVIDIA NIM

Use OpenAI-compatible endpoints with `OpenAICompatibleProvider`.

### Provider Factory

```python
from yom.providers import create_provider

# Auto-detect from model name
provider = create_provider(model="claude-3-5-sonnet")
provider = create_provider(model="gpt-4o-mini")

# Explicit
provider = create_provider(provider="anthropic", api_key="sk-...")
```

---

## Testing

### Fake Agent

```python
from yom.testing import fake_agent

agent = fake_agent("I am a test agent")
result = agent.run_sync("Who are you?")
assert "test agent" in result
```

### Mock Provider

```python
from yom.testing import MockProvider, fake_agent

provider = MockProvider(responses=[
    "First response",
    "Second response",
    "Third response"
])

agent = fake_agent(provider=provider)

r1 = agent.run_sync("Q1")  # "First response"
r2 = agent.run_sync("Q2")  # "Second response"
```

### Assertions

```python
from yom.testing import assert_response

assert_response("Hello world", contains="Hello")
assert_response("abc123", matches=r"\d+")
assert_response("test", min_length=3, max_length=10)
```

### Test Suite

```python
from yom.testing import TestSuite, AgentTestCase, run_test_suite

suite = TestSuite(
    name="greeting_tests",
    cases=[
        AgentTestCase(
            name="basic_greeting",
            prompt="Say hello",
            expected_contains=["hello", "Hi"]
        ),
        AgentTestCase(
            name="name_greeting",
            prompt="Greet Alice",
            expected_contains=["Alice"]
        ),
    ]
)

results = await run_test_suite(agent, suite)
print(f"Passed: {results['passed']}, Failed: {results['failed']}")
```

---

## Debugging

### Enable Debug Mode

```python
import os
os.environ["YOM_DEBUG"] = "1"

# Or programmatically
from yom.debug import enable_debug
enable_debug()
```

### Trace Execution

```python
from yom.debug import trace

with trace("my_operation") as ctx:
    result = agent.run("Do something")
    print(f"Duration: {ctx.duration}")
```

### View Traces

```python
from yom.debug import get_recorder

recorder = get_recorder()
for event in recorder.events:
    print(event)
```

### Inspect State

```python
from yom.debug import inspect_state

info = inspect_state(agent._runtime._state)
print(info)
```

---

## Telegram Bot

Telegram helpers are not included in the core package. Integrate your preferred Telegram SDK and call `agent.run(...)` in your handlers.

---

## Web Scraping

```python
from yom import Agent

agent = Agent(tools=["core", "http_request"])

result = agent.run_sync("""
Fetch the title from https://example.com
""")
```

### Fetch JSON

```python
agent = Agent(tools=["core"])
result = agent.run_sync("""
Get the current BTC price from https://api.coindesk.com/v1/bpi/currentprice.json
Extract and return the price.
""")
```

---

## Database Operations

### Query Database

```python
from yom import Agent

agent = Agent(tools=["core", "query_db"])

result = agent.run_sync("""
Query the database: SELECT * FROM users WHERE active = true LIMIT 10
Connection: postgresql://localhost/mydb
""")
```

### Dry Run (Safe)

```python
result = agent.run_sync("""
Dry run: DELETE FROM users
""")
# Returns validation without executing
```

---

## File Operations

### Read Files

```python
from yom import Agent

agent = Agent(tools=["core"])

result = agent.run_sync("""
Read the file at /path/to/file.txt
""")
```

### Write Files

```python
agent.run_sync("""
Write "Hello, World!" to /tmp/output.txt
""")
```

### Edit Files

```python
agent.run_sync("""
Edit /path/to/file.txt:
- Find "old text"
- Replace with "new text"
""")
```

---

## Code Examples

### RAG (Retrieval Augmented Generation)

```python
from yom import Agent

agent = Agent(tools=["core"])

# Load documents into context
docs = [
    open("doc1.txt").read(),
    open("doc2.txt").read(),
]

result = agent.run(f"""
Based on these documents:
{docs}

Answer: What is the main topic?
""")
```

### Multi-Agent

```python
from yom import Agent

# Supervisor agent
supervisor = Agent(
    system_prompt="You coordinate other agents.",
    tools=["core"]
)

# Specialized agents
coder = Agent(system_prompt="You write code.", tools=["core", "bash"])
reviewer = Agent(system_prompt="You review code.", tools=["core"])

result = supervisor.run("""
Have the coder write a hello world function,
then have the reviewer check it.
""")
```

### Stateful Assistant

```python
from yom import Agent

assistant = Agent(
    session_id="user-preferences",
    system_prompt="Remember all user preferences."
)

assistant.run("I prefer dark mode")
assistant.run("My name is Alice")
assistant.run("I like blue color")

# Later - remembers everything
assistant.run("What are my preferences?")
# → "You prefer dark mode, your name is Alice, and you like blue."
```

---

## Performance Tips

### Parallel Tool Calls

```python
# Agent can call multiple tools in parallel
agent.run("""
Make 3 API calls simultaneously:
1. Get user data from /api/users/1
2. Get posts from /api/posts
3. Get comments from /api/comments
""")
```

### Batch Processing

```python
import asyncio
from yom import Agent

async def process_batch(items):
    agent = Agent(tools=["core"])
    tasks = [agent.run(f"Process: {item}") for item in items]
    return await asyncio.gather(*tasks)

results = asyncio.run(process_batch(["item1", "item2", "item3"]))
```

### Context Management

```python
from yom import Agent
from yom.context import ContextManager

manager = ContextManager(max_tokens=4000)

agent = Agent(
    tools=["core"],
    max_context_tokens=4000  # Limit context size
)
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install yom[telegram]
COPY bot.py .
CMD ["python", "bot.py"]
```

### Environment Variables

```bash
# Required for AI
export OPENAI_API_KEY="sk-..."

# Optional
export MINIMAX_API_KEY="..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Telegram
export TELEGRAM_BOT_TOKEN="123:abc"

# Debug
export YOM_DEBUG="1"
```

### systemd Service

```ini
[Unit]
Description=yom Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
Environment=OPENAI_API_KEY=sk-...
Environment=TELEGRAM_BOT_TOKEN=123:abc
ExecStart=/usr/local/bin/yom telegram polling --token $TELEGRAM_BOT_TOKEN
Restart=always

[Install]
WantedBy=multi-user.target
```
