---
name: coding
description: Best practices for Python code generation
---

# Coding Skill

Follow these guidelines when writing Python code.

## Style

- 4 spaces for indentation
- 88 character line limit (Black formatter)
- snake_case for functions and variables
- PascalCase for classes
- UPPER_SNAKE_CASE for constants

## Type Hints

Always use type hints. Avoid `Any` unless absolutely necessary.

```python
# Good
def get_user(user_id: int) -> User | None:
    ...

# Bad - no type hints
def get_user(user_id):
    ...
```

## Docstrings

Use Google-style docstrings for all public APIs:

```python
def process_data(items: list[str]) -> dict[str, int]:
    """Process a list of items into counts.
    
    Args:
        items: List of string items to count
        
    Returns:
        Dictionary mapping items to their occurrence count
    """
```

## Imports

Sort imports in groups:
1. Standard library
2. Third-party
3. Local

```python
import json
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from myapp.models import User
```

## Error Handling

```python
# Good
try:
    result = process(data)
except ValueError as e:
    raise ProcessingError(f"Failed to process: {e}") from e

# Bad - bare except
try:
    result = process(data)
except:
    pass
```

## Testing

Write tests with pytest:

```python
def test_process_data():
    result = process_data(["a", "b", "a"])
    assert result == {"a": 2, "b": 1}
```

## File Structure

Keep files under 300 lines. One class per file unless tightly coupled.
