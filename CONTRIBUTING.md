# Contributing

## Setup

```bash
uv sync --all-extras
```

## Checks

```bash
uv run python -m compileall -q yom tests examples *.py
uv run ruff check .
uv run pytest -q
```

## Guidelines

- Keep API/docs in sync.
- Add tests for behavior changes.
- Prefer backward-compatible changes when possible.
