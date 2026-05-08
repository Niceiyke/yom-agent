# Skills

**Reusable prompt templates loaded on demand.**

Skills let you define specialized instructions once, then load them when needed.

## Overview

```
Agent system prompt:
"Available skills: coding, research, writing"

User: "Write me a web scraper"

Agent decides to load coding skill:
→ Calls load_skill(name="coding")
→ Full coding guidelines appended to context
→ Writes code following those guidelines
```

vs. copy-pasting guidelines into every prompt.

## How It Works

1. **Create** skill files in a skills directory
2. **Discover** - yom scans standard paths automatically
3. **Catalog** - Agent sees available skills in system prompt
4. **Load** - Agent calls `load_skill` when ready

## Discovery Paths

Skills are discovered in this order:

1. `~/.yom/skills/` - User-level skills
2. `{cwd}/skills/` - Project skills
3. `{cwd}/.yom/skills/` - Project skills (alternative)
4. Explicit `skill_paths` argument

## Directory Structure

```
skills/
├── coding/
│   └── SKILL.md           # Required filename
├── research/
│   └── SKILL.md
└── writing/
    └── SKILL.md

# Or flat:
skills/
├── python-best-practices.md
└── api-design.md
```

## Creating Skills

### Basic Skill

**`skills/coding/SKILL.md`**
```markdown
---
name: coding
description: Best practices for Python code generation
---

# Coding Skill

When writing Python code:

1. Use type hints on all functions
2. Add docstrings to public APIs
3. Follow PEP 8 style
4. Write pytest tests

## Template

```python
def function_name(param: Type) -> ReturnType:
    '''Describe what this does.
    
    Args:
        param: What this parameter is
        
    Returns:
        What this returns
    '''
    pass
```
```

### Skill with Options

**`skills/research/SKILL.md`**
```markdown
---
name: research
description: Guidelines for web research tasks
disable-model-invocation: true
---

# Research Skill

When researching a topic:

1. Use multiple sources
2. Verify claims with primary sources
3. Note publication dates
4. Distinguish facts from opinions

## Source Priority

1. Official documentation
2. Peer-reviewed papers
3. Established news sources
4. Community discussions
```

### Skill Frontmatter

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Skill identifier (must match parent directory) |
| `description` | string | Yes | Shown in skills catalog |
| `disable-model-invocation` | bool | No | Hide from catalog if true |

### Naming Rules

- Must match parent directory name: `skills/coding/SKILL.md` → name is `coding`
- Max 64 characters
- Lowercase alphanumeric with hyphens only
- No leading/trailing hyphens
- No consecutive hyphens

## Loading Skills

### Automatic (via Agent)

Skills are automatically discovered and cataloged:

```python
from yom import Agent

# Discover skills from standard paths
loaded = load_skills(cwd=".")
print(f"Found {len(loaded.skills)} skills: {[s.name for s in loaded.skills]}")

# Agent sees them in system prompt
agent = Agent(tools=["core"])
# System prompt includes:
# "<available_skills>..."
```

### Manual Discovery

```python
from yom.skills import load_skills, format_skills_for_prompt

# Load from specific paths
loaded = load_skills(
    cwd="/path/to/project",
    skill_paths=["/custom/skills/path"],
    include_defaults=True,
)

# Format for system prompt
catalog = format_skills_for_prompt(loaded.skills)
```

### Programmatic Loading

```python
from yom.skills import get_skill_content, append_skill_to_state

# Get skill content
skill = loaded.skills[0]
content = get_skill_content(skill)

# Append to agent state
append_skill_to_state(agent.state, skill, content)
```

## The `load_skill` Tool

When skills are enabled, the agent has access to:

```python
LOAD_SKILL_SCHEMA = {
    "name": "load_skill",
    "description": "Load a relevant skill's full instructions...",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
}
```

The agent calls this when starting a task that matches a skill.

### Tool Implementation

```python
async def load_skill_tool(input_data: dict, state: Any, cwd: str | None = None) -> str:
    name = input_data.get("name")
    
    if name in getattr(state, "loaded_skills", []):
        return f"Skill already loaded: {name}"
    
    loaded = load_skills(cwd=cwd)
    skill = by_name.get(name)
    
    if skill is None:
        return f"Unknown skill: {name}. Available: {available}"
    
    content = get_skill_content(skill)
    append_skill_to_state(state, skill, content)
    
    return f"Loaded skill: {skill.name}"
```

## Example: Coding Agent

### 1. Create skill

**`skills/coding/SKILL.md`**
```markdown
---
name: coding
description: Python coding best practices
---

# Coding Skill

## Style

- 4 spaces, 88 char lines
- snake_case for functions
- PascalCase for classes

## Type Hints

All function signatures need type hints:

```python
def process(items: list[str]) -> dict[str, int]:
    ...
```

## Docstrings

Google-style docstrings:

```python
def calculate(x: float, y: float) -> float:
    """Calculate result of operation.
    
    Args:
        x: First operand
        y: Second operand
        
    Returns:
        The calculated result
        
    Raises:
        ValueError: If inputs invalid
    """
```

## Testing

Write pytest tests:

```python
def test_calculate_basic():
    assert calculate(1.0, 2.0) == 3.0

def test_calculate_invalid():
    with pytest.raises(ValueError):
        calculate(0, 0)
```
```

### 2. Create agent

**`agent.py`**
```python
from yom import Agent
from yom.skills import load_skills, format_skills_for_prompt

# Load skills at startup
loaded = load_skills(cwd=".")
skills_catalog = format_skills_for_prompt(loaded.skills)

system_prompt = f"""You are a coding assistant.

{skills_catalog}

Call load_skill(name="coding") before writing any code.
"""

agent = Agent(
    tools=["core", "spawn"],  # spawn for sub-agents if needed
    system_prompt=system_prompt,
)

async def main():
    result = await agent.run("Write a function to parse CSV files")
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Skill vs Sub-agent

| Aspect | Skill | Sub-agent |
|--------|-------|-----------|
| **Purpose** | Prompt template | Spawnable specialist |
| **Loads into** | System prompt | New agent instance |
| **Use case** | Guidelines, standards | Specialized execution |
| **State** | Appended to current context | Fresh context |
| **Cost** | Low (just prompt text) | Higher (new LLM call) |

**Use Skills for:**
- Coding standards
- Writing style guides
- Research methodologies
- Any reusable guidelines

**Use Sub-agents for:**
- Code review (different model, fresh perspective)
- Long-running tasks
- Tasks requiring specific tools
- Parallel execution

## Sharing Skills

Skills can be shared via packages:

```python
# my-company-skills/setup.py
from setuptools import setup

setup(
    name="my-company-skills",
    package_data={"my_company_skills": ["skills/**/*.md"]},
)
```

Users install and skills auto-discover:
```bash
pip install my-company-skills
# → ~/.yom/skills/ now includes your skills
```

## Validation

yom validates skills on load:

```python
loaded = load_skills(cwd=".")

for diag in loaded.diagnostics:
    if diag["type"] == "warning":
        print(f"Warning: {diag['message']} ({diag['path']})")
```

Common warnings:
- Missing description
- Name doesn't match directory
- Description too long (>1024 chars)
