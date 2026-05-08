# Examples

## Production Examples

Real examples with LLM API calls in `production/`:

- [`production/customer_support.py`](production/customer_support.py) - Structured support with Pydantic output
- [`production/code_review_pipeline.py`](production/code_review_pipeline.py) - Multi-agent pipeline

```bash
export MINIMAX_API_KEY=your_key  # or OPENAI_API_KEY
python examples/production/customer_support.py
```

## Agent Definitions

Sub-agents defined as Markdown in `agents/`:

- [`agents/python-expert.md`](agents/python-expert.md) - General Python tasks
- [`agents/researcher.md`](agents/researcher.md) - Web research

## Other Examples

| File | Description |
|------|-------------|
| `multi_agent_demo.py` | Sub-agent spawning demo |
| `customer_support.py` | Support agent with tools |
| `pydantic_validation.py` | Pydantic tool patterns |
| `demo_new_features.py` | Feature demonstrations |
| `colab/` | Jupyter notebooks |

## Running Examples

```bash
# Simple demo
python examples/multi_agent_demo.py --simple

# With sub-agents
python examples/multi_agent_demo.py

# Customer support
python examples/production/customer_support.py

# Code review pipeline
python examples/production/code_review_pipeline.py
```
