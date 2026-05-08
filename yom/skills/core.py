"""Skills system for discovery, prompt catalogs, and runtime loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024

LOAD_SKILL_SCHEMA: dict[str, Any] = {
    "name": "load_skill",
    "description": "Load a relevant skill's full instructions into persistent context before following that skill workflow.",
    "input_schema": {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Exact skill name from the available skills catalog."}},
        "required": ["name"],
    },
}


class Skill(BaseModel):
    """A discoverable skill with metadata and content."""
    name: str
    description: str
    file_path: Path
    base_dir: Path
    source: str
    disable_model_invocation: bool = False

    model_config = {"arbitrary_types_allowed": True}


class LoadedSkills(BaseModel):
    """Container for discovered skills and diagnostics."""
    skills: list[Skill] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


def _validate_name(name: str, parent_dir_name: str) -> list[str]:
    """Validate skill name matches directory and follows naming rules."""
    errors = []
    if name != parent_dir_name:
        errors.append(f"name '{name}' does not match parent directory '{parent_dir_name}'")
    if len(name) > MAX_NAME_LENGTH:
        errors.append(f"name exceeds {MAX_NAME_LENGTH} characters ({len(name)})")
    if not name.replace("-", "").isalnum():
        errors.append("name must be lowercase alphanumeric with hyphens only")
    if name.startswith("-") or name.endswith("-"):
        errors.append("name must not start or end with a hyphen")
    if "--" in name:
        errors.append("name must not contain consecutive hyphens")
    return errors


def _validate_description(description: str | None) -> list[str]:
    """Validate skill description."""
    errors = []
    if not description or not description.strip():
        errors.append("description is required")
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append(f"description exceeds {MAX_DESCRIPTION_LENGTH} characters ({len(description)})")
    return errors


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-like frontmatter from skill file."""
    lines = content.split("\n")
    if not lines or lines[0] != "---":
        return {}, content

    end_idx = -1
    for i, line in enumerate(lines[1:], 1):
        if line == "---":
            end_idx = i
            break

    if end_idx == -1:
        return {}, content

    frontmatter: dict[str, Any] = {}
    for line in lines[1:end_idx]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip()

    body = "\n".join(lines[end_idx + 1:])
    return frontmatter, body


def _load_skill_from_file(file_path: Path, source: str) -> tuple[Skill | None, list[dict[str, Any]]]:
    """Load a single skill from a file."""
    diagnostics: list[dict[str, Any]] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        diagnostics.append({"type": "warning", "message": str(e), "path": str(file_path)})
        return None, diagnostics

    frontmatter, _body = _parse_frontmatter(content)
    skill_dir = file_path.parent
    parent_dir_name = skill_dir.name

    name = frontmatter.get("name") or parent_dir_name
    description = frontmatter.get("description", "")

    name_errors = _validate_name(name, parent_dir_name)
    for error in name_errors:
        diagnostics.append({"type": "warning", "message": error, "path": str(file_path)})

    desc_errors = _validate_description(description)
    for error in desc_errors:
        diagnostics.append({"type": "warning", "message": error, "path": str(file_path)})

    if desc_errors and not description:
        return None, diagnostics

    return Skill(
        name=name,
        description=description,
        file_path=file_path,
        base_dir=skill_dir,
        source=source,
        disable_model_invocation=frontmatter.get("disable-model-invocation", False) is True,
    ), diagnostics


def _scan_dir_for_skills(dir_path: Path, source: str) -> tuple[list[Skill], list[dict[str, Any]]]:
    """Recursively scan directory for skill files."""
    skills: list[Skill] = []
    diagnostics: list[dict[str, Any]] = []

    if not dir_path.exists():
        return skills, diagnostics

    for entry in dir_path.iterdir():
        if entry.is_symlink():
            try:
                if not entry.resolve().is_file():
                    continue
            except (OSError, ValueError):
                continue

        if entry.name == "SKILL.md" and entry.is_file():
            skill, diags = _load_skill_from_file(entry, source)
            if skill:
                skills.append(skill)
            diagnostics.extend(diags)
            return skills, diagnostics

    for entry in dir_path.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.name == "node_modules":
            continue

        if entry.is_dir():
            sub_skills, sub_diags = _scan_dir_for_skills(entry, source)
            skills.extend(sub_skills)
            diagnostics.extend(sub_diags)
        elif entry.is_file() and entry.suffix == ".md":
            skill, diags = _load_skill_from_file(entry, source)
            if skill:
                skills.append(skill)
            diagnostics.extend(diags)

    return skills, diagnostics


def load_skills(
    cwd: Path | str | None = None,
    user_dir: Path | str | None = None,
    skill_paths: list[Path | str] | None = None,
    include_defaults: bool = True,
) -> LoadedSkills:
    """Discover all available skills.

    Search order:
    1. ~/.yom/skills/ (user skills, if include_defaults=True)
    2. {cwd}/skills/ (project skills)
    3. {cwd}/.yom/skills/ (project skills, alt)
    4. skill_paths (explicit paths)

    Args:
        cwd: Current working directory for project skills discovery
        user_dir: User directory for user skills (default: ~/.yom)
        skill_paths: Explicit paths to scan for skills
        include_defaults: Whether to include user/project default skills

    Returns:
        LoadedSkills with discovered skills and any diagnostics
    """
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    if user_dir is None:
        user_dir = Path.home() / ".yom"
    user_dir = Path(user_dir)

    all_skills: list[Skill] = []
    all_diagnostics: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    def add_skills(skills: list[Skill]) -> None:
        for skill in skills:
            real_path = str(skill.file_path.resolve())
            if real_path in seen_paths:
                continue
            seen_paths.add(real_path)
            all_skills.append(skill)

    if include_defaults:
        user_skills_dir = user_dir / "skills"
        if user_skills_dir.exists():
            skills, diags = _scan_dir_for_skills(user_skills_dir, "user")
            add_skills(skills)
            all_diagnostics.extend(diags)

        for project_skills_dir in (cwd / "skills", cwd / ".yom" / "skills"):
            if project_skills_dir.exists():
                skills, diags = _scan_dir_for_skills(project_skills_dir, "project")
                add_skills(skills)
                all_diagnostics.extend(diags)

    if skill_paths:
        for path in skill_paths:
            path = Path(path)
            if not path.exists():
                all_diagnostics.append({"type": "warning", "message": "skill path does not exist", "path": str(path)})
                continue

            if path.is_dir():
                skills, diags = _scan_dir_for_skills(path, "path")
                add_skills(skills)
                all_diagnostics.extend(diags)
            elif path.is_file() and path.suffix == ".md":
                skill, diags = _load_skill_from_file(path, "path")
                if skill:
                    add_skills([skill])
                all_diagnostics.extend(diags)

    return LoadedSkills(skills=all_skills, diagnostics=all_diagnostics)


def format_skills_for_prompt(skills: list[Skill]) -> str:
    """Format skills for inclusion in system prompt.

    Creates a catalog of available skills that the LLM can use
    to decide which skill to load via load_skill tool.
    """
    visible_skills = [s for s in skills if not s.disable_model_invocation]

    if not visible_skills:
        return ""

    lines = [
        "\n\nThe following skills provide specialized instructions for specific tasks.",
        "Call `load_skill` with the exact skill name before following a skill's full workflow.",
        "When a skill file references a relative path, resolve it against the skill directory.",
        "",
        "<available_skills>",
    ]

    for skill in visible_skills:
        safe_name = skill.name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_desc = skill.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_path = str(skill.file_path).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append("  <skill>")
        lines.append(f"    <name>{safe_name}</name>")
        lines.append(f"    <description>{safe_desc}</description>")
        lines.append(f"    <location>{safe_path}</location>")
        lines.append("  </skill>")

    lines.append("</available_skills>")
    return "\n".join(lines)


def get_skill_content(skill: Skill) -> str:
    """Get the full content of a skill file (including frontmatter)."""
    return skill.file_path.read_text(encoding="utf-8")


def append_skill_to_state(
    state: Any,
    skill: Skill,
    content: str,
    loaded_skills_attr: str = "loaded_skills",
    system_prompt_attr: str = "system_prompt",
) -> None:
    """Append skill content to agent state.

    Args:
        state: Agent state object (must have loaded_skills list and system_prompt str)
        skill: Skill to append
        content: Full skill content
        loaded_skills_attr: Name of the attribute holding loaded skill names
        system_prompt_attr: Name of the system prompt attribute
    """
    loaded_list = getattr(state, loaded_skills_attr, None)
    if loaded_list is None:
        loaded_list = []
        setattr(state, loaded_skills_attr, loaded_list)

    if skill.name in loaded_list:
        return

    loaded_list.append(skill.name)
    current_prompt = getattr(state, system_prompt_attr, "")
    new_prompt = current_prompt + (
        f"\n\n# Loaded Skill: {skill.name}\n\n"
        f"Source: {skill.file_path}\n\n"
        f"{content.strip()}"
    )
    setattr(state, system_prompt_attr, new_prompt)
