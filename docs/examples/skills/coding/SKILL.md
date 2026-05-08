---
name: coding
description: Best practices for Python code generation
---

# Coding Skill

Load this skill when generating Python code. Follow these guidelines strictly.

## Style

### PEP 8
- 4 spaces for indentation
- Max line length: 88 characters
- Two blank lines between top-level definitions
- One blank line between method definitions in classes

### Naming
| Type | Convention | Example |
|------|------------|---------|
| Function | snake_case | `process_data` |
| Class | PascalCase | `DataProcessor` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| Private method | _leading_underscore | `_validate` |

## Type Hints

Always use type hints. Avoid `Any` unless absolutely necessary.

```python
# Good
def get_user(user_id: int) -> User | None:
    ...

# Bad
def get_user(user_id):
    ...
```

## Docstrings

Use Google-style docstrings for all public APIs:

```python
def calculate_stats(numbers: list[float]) -> dict[str, float]:
    """Calculate basic statistics for a list of numbers.
    
    Args:
        numbers: List of numeric values to analyze
        
    Returns:
        Dictionary with keys: mean, median, std_dev
        
    Example:
        >>> calculate_stats([1.0, 2.0, 3.0])
        {'mean': 2.0, 'median': 2.0, 'std_dev': 1.0}
    """
```

## Error Handling

```python
# Good - specific exception with context
def parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON at position {e.pos}") from e

# Bad - bare except, swallowing exception
def parse_json(text: str):
    try:
        return json.loads(text)
    except:
        return {}
```

## Testing

Write tests first (TDD) or alongside code:

```python
import pytest

class TestDataProcessor:
    def test_process_basic(self):
        processor = DataProcessor()
        result = processor.process([1, 2, 3])
        assert result == [2, 4, 6]
    
    def test_process_empty(self):
        processor = DataProcessor()
        result = processor.process([])
        assert result == []
```

## Async

Use `anyio` for async-agnostic code:

```python
from anyio import to_thread
import aiofiles

async def read_file(path: str) -> str:
    async with aiofiles.open(path) as f:
        return await f.read()
```

## Imports

```python
# Standard library
import json
from pathlib import Path
from typing import Optional

# Third-party
import httpx
from pydantic import BaseModel

# Local
from myapp.models import User
from myapp.utils import validate_email
```

## File Organization

```
package/
├── __init__.py          # Public exports only
├── models.py            # Pydantic models
├── types.py             # Type aliases
├── core.py              # Main logic
├── utils.py             # Helper functions
└── exceptions.py        # Custom exceptions
```
