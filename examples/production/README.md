# Production Examples

Real-world examples with actual LLM calls.

## Prerequisites

Set your API key:
```bash
export MINIMAX_API_KEY=your_key  # or OPENAI_API_KEY
export YOM_MODEL=gpt-4o-mini     # optional: specify model
```

## Examples

### Customer Support Agent

Structured support agent with Pydantic output validation.

```bash
python examples/production/customer_support.py
```

Features:
- Structured JSON responses
- Tool-based operations (lookup, refund, ticket creation)
- Session persistence

### Code Review Pipeline

Multi-agent pipeline with sub-agents.

```bash
python examples/production/code_review_pipeline.py
```

Features:
- Sub-agent spawning (coder + reviewer)
- Skills loading
- Context passing between agents

### Multi-Agent Demo

Basic demo of sub-agents.

```bash
python examples/multi_agent_demo.py
```

Or simple mode:
```bash
python examples/multi_agent_demo.py --simple
```

## Notes

- These examples make real LLM API calls
- Costs depend on your provider
- Sessions persist to `.yom/sessions/` by default
- Add `--session <name>` to continue a session
