"""Core tools for file operations and command execution."""

from __future__ import annotations

import asyncio
import shlex
from pathlib import Path

from yom.tools import tool

ALLOWED_DIRS = {"~": Path.home()}


def _validate_path(path: str, base_dir: str = "~") -> Path | str:
    """Validate path stays within allowed base directory."""
    file_path = Path(path).expanduser().resolve()
    base = ALLOWED_DIRS.get(base_dir, Path(base_dir).expanduser().resolve())
    try:
        file_path.relative_to(base)
        return file_path
    except ValueError:
        return f"Error: Path '{path}' escapes allowed directory '{base_dir}'"


@tool(name="read", description="Read the contents of a file. Returns the file content or error message.")
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        validated = _validate_path(path)
        if isinstance(validated, str):
            return validated
        if not validated.exists():
            return f"Error: File not found: {path}"
        if not validated.is_file():
            return f"Error: Not a file: {path}"
        return validated.read_text()
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


@tool(name="write", description="Write content to a file. Creates the file if it doesn't exist.")
def write_file(path: str, content: str) -> str:
    """Write content to a file at the given path."""
    try:
        validated = _validate_path(path)
        if isinstance(validated, str):
            return validated
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
    try:
        validated = _validate_path(path)
        if isinstance(validated, str):
            return validated
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


@tool(name="bash", description="Execute a bash command and return the output. WARNING: Use with caution - commands run with user permissions.")
async def bash(command: str, cwd: str | None = None, timeout: int = 30) -> str:
    """Execute a bash command and return stdout/stderr."""
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
        output = stdout.decode() if stdout else ""
        err = stderr.decode() if stderr else ""

        if result.returncode != 0:
            return f"[Exit code: {result.returncode}]\n{err or output}"
        return output or "Command executed successfully (no output)"
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


@tool(name="cmd", description="Execute a Windows command and return the output.")
async def cmd(command: str, timeout: int = 30) -> str:
    """Execute a Windows cmd command and return stdout/stderr."""
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
        output = stdout.decode() if stdout else ""
        err = stderr.decode() if stderr else ""

        if result.returncode != 0:
            return f"[Exit code: {result.returncode}]\n{err or output}"
        return output or "Command executed successfully (no output)"
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


CORE_TOOLS = [read_file, write_file, edit_file, bash, cmd]
CORE_TOOL_NAMES = {"read", "write", "edit", "bash", "cmd"}


def get_tool(name: str):
    """Get a core tool by name."""
    for t in CORE_TOOLS:
        if getattr(t, "_tool_name", t.__name__) == name:
            return t
    return None