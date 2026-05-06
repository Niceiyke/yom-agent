"""Skills system for yom."""

from __future__ import annotations

from typing import Any

from yom.skills.core import (
    Skill,
    LoadedSkills,
    load_skills,
    format_skills_for_prompt,
    get_skill_content,
    append_skill_to_state,
    LOAD_SKILL_SCHEMA,
)

__all__ = [
    "Skill",
    "LoadedSkills",
    "load_skills",
    "format_skills_for_prompt",
    "get_skill_content",
    "append_skill_to_state",
    "LOAD_SKILL_SCHEMA",
]


async def load_skill_tool(input_data: dict, state: Any, cwd: str | None = None) -> str:
    """Tool function to load a skill into agent state.

    Args:
        input_data: Tool input with 'name' key for skill name
        state: Agent state (must have loaded_skills and system_prompt)
        cwd: Optional working directory for skill discovery

    Returns:
        Success or error message
    """
    from pathlib import Path
    from yom.skills.core import load_skills, append_skill_to_state, get_skill_content

    name = input_data.get("name")
    if not isinstance(name, str) or not name:
        return "Tool error: name must be a non-empty string"

    loaded_skills = getattr(state, "loaded_skills", None)
    if loaded_skills is None:
        loaded_skills = []
        state.loaded_skills = loaded_skills

    if name in loaded_skills:
        return f"Skill already loaded: {name}"

    search_cwd = Path(cwd) if cwd else Path.cwd()
    loaded = load_skills(cwd=search_cwd)
    by_name = {skill.name: skill for skill in loaded.skills}
    skill = by_name.get(name)

    if skill is None:
        available = ", ".join(sorted(by_name.keys())) or "none"
        return f"Tool error: unknown skill: {name}. Available skills: {available}"

    try:
        content = get_skill_content(skill)
    except OSError as exc:
        return f"Tool error: {exc}"

    append_skill_to_state(state, skill, content)
    return f"Loaded skill: {skill.name}"
