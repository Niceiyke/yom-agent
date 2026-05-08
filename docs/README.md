# Documentation

## Getting Started

- [Quick Start](quickstart.md) - Get up and running in 5 minutes
- [Architecture](architecture.md) - Deep dive into yom's design

## Core Features

- [Sub-agents](subagents.md) - Spawnable specialists from Markdown files
- [Skills](skills.md) - Loadable prompt templates
- [Plugins](plugins.md) - Hot-reloadable extensions

## Reference

- [Tools](architecture.md#5-tools) - Type-safe tool definitions
- [Sessions](architecture.md#4-sessions) - Conversation memory
- [Events](architecture.md#7-events) - Lifecycle monitoring
- [Hooks](architecture.md#8-hooks) - Tool access control
- [Providers](architecture.md#6-providers) - Multi-provider support

## Examples

**Production examples** (with real LLM calls):

- [`examples/production/customer_support.py`](examples/production/customer_support.py) - Structured support with Pydantic output
- [`examples/production/code_review_pipeline.py`](examples/production/code_review_pipeline.py) - Multi-agent pipeline
- [`examples/multi_agent_demo.py`](examples/multi_agent_demo.py) - Sub-agent spawning demo

**Example agents** (Markdown definitions):

- [`examples/agents/python-expert.md`](examples/agents/python-expert.md) - General Python tasks
- [`examples/agents/researcher.md`](examples/agents/researcher.md) - Web research

**Example skills**:

- [`examples/.yom/skills/coding/SKILL.md`](../examples/.yom/skills/coding/SKILL.md)
