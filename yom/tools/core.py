"""Core tools for file operations and command execution."""

from __future__ import annotations

import asyncio
import glob as glob_module

import re
import shlex
from pathlib import Path
from typing import Any

from yom.tools import tool

ALLOWED_DIRS = {"~": Path.home(), "/tmp": Path("/tmp")}
ALLOWED_COMMANDS: list[str] | None = None


def set_allowed_commands(commands: list[str] | None) -> None:
    """Set list of allowed bash commands (for security)."""
    global ALLOWED_COMMANDS
    ALLOWED_COMMANDS = commands


def _validate_path(path: str, base_dir: str = "~") -> Path | str:
    """Validate path stays within allowed base directory."""
    abs_path = Path(path).expanduser().resolve()
    base = ALLOWED_DIRS.get(base_dir, Path(base_dir).expanduser().resolve())

    if not str(abs_path).startswith(str(base)):
        for allowed_base in ALLOWED_DIRS.values():
            if str(abs_path).startswith(str(allowed_base)):
                return abs_path
        # Check protected directories
        protected = {"/etc", "/sys", "/proc"}
        for prot in protected:
            if abs_path.is_relative_to(Path(prot)):
                return f"Error: Path '{path}' is in a protected directory"
        return f"Error: Path '{path}' escapes allowed directory '{base_dir}'"
    return abs_path


def _validate_command(command: str) -> str | None:
    """Validate bash command against allowed list if configured."""
    if ALLOWED_COMMANDS is None:
        return None

    safe_commands = {"ls", "cat", "head", "tail", "grep", "find", "pwd", "cd", "echo", "printf", "wc", "sort", "uniq", "awk", "sed"}
    tokens = shlex.split(command)
    if not tokens:
        return "Error: Empty command"
    base_cmd = tokens[0]
    if base_cmd not in safe_commands:
        return f"Error: Command '{base_cmd}' not allowed. Allowed: {', '.join(sorted(safe_commands))}"
    return None


DANGEROUS_PATTERNS = [
    r"\.\./",
    r"\|\s*rm",
    r";\s*rm",
    r"&\s*rm",
    r"rm\s+-rf",
    r">\s*/dev/sd",
    r"dd\s+if=.*of=/dev/",
]


def _check_dangerous_patterns(command: str) -> str | None:
    """Check for obviously dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Error: Command contains potentially dangerous pattern: {pattern}"
    return None


@tool(name="read", description="Read the contents of a file. Returns the file content or error message.")
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    validated = _validate_path(path)
    if isinstance(validated, str):
        return validated
    try:
        if not validated.exists():
            return f"Error: File not found: {path}"
        if not validated.is_file():
            return f"Error: Not a file: {path}"
        return validated.read_text(errors="replace")
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


@tool(name="write", description="Write content to a file. Creates the file if it doesn't exist.")
def write_file(path: str, content: str) -> str:
    """Write content to a file at the given path."""
    validated = _validate_path(path)
    if isinstance(validated, str):
        return validated
    try:
        validated.parent.mkdir(parents=True, exist_ok=True)
        validated.write_text(content)
        return f"Successfully wrote to {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error writing to {path}: {e}"


@tool(name="edit", description="Edit a file by replacing old_string with new_string. Returns success or error.")
def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Replace old_string with new_string in a file."""
    validated = _validate_path(path)
    if isinstance(validated, str):
        return validated
    try:
        if not validated.exists():
            return f"Error: File not found: {path}"

        content = validated.read_text()

        if old_string not in content:
            return f"Error: old_string not found in file. Content length: {len(content)}"

        new_content = content.replace(old_string, new_string, 1)
        validated.write_text(new_content)
        return f"Successfully edited {path}"
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error editing {path}: {e}"


@tool(
    name="bash",
    description="Execute a bash command and return the output. WARNING: Use with caution - commands run with user permissions.",
    schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
            },
        },
        "required": ["command"],
    },
)
async def bash(command: str, cwd: str | None = None, timeout: int = 30) -> str:
    """Execute a bash command and return stdout/stderr."""
    error = _check_dangerous_patterns(command)
    if error:
        return error

    error = _validate_command(command)
    if error:
        return error

    if timeout > 120:
        return f"Error: Timeout cannot exceed 120 seconds (got {timeout})"

    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            ),
            timeout=timeout,
        )
        stdout, stderr = await result.communicate()
        output = stdout.decode(errors="replace") if stdout else ""
        err = stderr.decode(errors="replace") if stderr else ""

        if result.returncode != 0:
            return f"[Exit code: {result.returncode}]\n{err or output}"
        return output or "Command executed successfully (no output)"
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout} seconds"
    except PermissionError:
        return f"Error: Permission denied to execute command"
    except Exception as e:
        return f"Error executing command: {e}"


@tool(
    name="cmd",
    description="Execute a Windows command and return the output.",
    schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The Windows command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
            },
        },
        "required": ["command"],
    },
)
async def cmd(command: str, timeout: int = 30) -> str:
    """Execute a Windows cmd command and return stdout/stderr."""
    if timeout > 120:
        return f"Error: Timeout cannot exceed 120 seconds (got {timeout})"

    try:
        result = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            ),
            timeout=timeout,
        )
        stdout, stderr = await result.communicate()
        output = stdout.decode(errors="replace") if stdout else ""
        err = stderr.decode(errors="replace") if stderr else ""

        if result.returncode != 0:
            return f"[Exit code: {result.returncode}]\n{err or output}"
        return output or "Command executed successfully (no output)"
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


@tool(name="grep", description="Search for pattern in files. Returns matching lines with context.")
def grep_files(
    pattern: str,
    path: str = ".",
    recursive: bool = True,
    file_pattern: str = "*",
) -> str:
    """Search for a regex pattern in files."""
    validated = _validate_path(path)
    if isinstance(validated, str):
        return validated

    search_path = validated if validated.is_dir() else validated.parent
    if not search_path.exists():
        return f"Error: Path does not exist: {path}"

    try:
        re.compile(pattern)
    except re.error as e:
        return f"Error: Invalid regex pattern: {e}"

    matches = []
    try:
        if recursive:
            files = search_path.rglob(file_pattern)
        else:
            files = search_path.glob(file_pattern)

        for f in files:
            if not f.is_file():
                continue
            try:
                content = f.read_text(errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line):
                        matches.append(f"{f}:{i}: {line.rstrip()}")
            except PermissionError:
                continue
            except Exception:
                continue
    except Exception as e:
        return f"Error searching files: {e}"

    if not matches:
        return f"No matches found for '{pattern}' in {path}"
    return "\n".join(matches[:100])


@tool(
    name="glob",
    description="Find files matching a glob pattern.",
    schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g., '**/*.py')",
            },
            "path": {
                "type": "string",
                "description": "Base directory to search in",
                "default": ".",
            },
        },
        "required": ["pattern"],
    },
)
def glob_files(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern."""
    validated = _validate_path(path)
    if isinstance(validated, str):
        return validated

    base = validated if validated.is_dir() else validated.parent
    try:
        matches = list(base.glob(pattern))
    except Exception as e:
        return f"Error finding files: {e}"

    if not matches:
        return f"No files found matching '{pattern}' in {path}"

    result = []
    for m in matches[:50]:
        try:
            rel = m.relative_to(base) if m.is_relative_to(base) else m
            result.append(str(rel))
        except ValueError:
            result.append(str(m))

    return "\n".join(result)


CORE_TOOLS = [read_file, write_file, edit_file, bash, cmd, grep_files, glob_files]
CORE_TOOL_NAMES = {"read", "write", "edit", "bash", "cmd", "grep", "glob"}


def get_tool(name: str):
    """Get a core tool by name."""
    for t in CORE_TOOLS:
        if getattr(t, "_tool_name", t.__name__) == name:
            return t
    return None