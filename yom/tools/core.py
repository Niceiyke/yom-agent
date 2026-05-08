"""Core tools for file operations and command execution."""

from __future__ import annotations

import asyncio
import re
import shlex
from pathlib import Path
from typing import Callable

from yom.tools.pydantic_tools import tool

ALLOWED_DIRS = {"~": Path.home(), "/tmp": Path("/tmp")}
ALLOWED_COMMANDS: list[str] | None = None


def _is_within(path: Path, base: Path) -> bool:
    """Return True if path is within base directory."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def set_allowed_commands(commands: list[str] | None) -> None:
    """Set list of allowed bash commands (for security)."""
    global ALLOWED_COMMANDS
    ALLOWED_COMMANDS = commands


def _validate_path(path: str, base_dir: str = "~") -> Path | str:
    """Validate path stays within allowed base directory."""
    abs_path = Path(path).expanduser().resolve()
    base = ALLOWED_DIRS.get(base_dir, Path(base_dir).expanduser().resolve())

    if not _is_within(abs_path, base):
        for allowed_base in ALLOWED_DIRS.values():
            if _is_within(abs_path, allowed_base):
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


# =============================================================================
# Tool Factory Functions - P1
# Create tools with custom cwd instead of hardcoded Path.cwd()
# =============================================================================

def create_read_tool(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
) -> Callable[[str], str]:
    """Create a read tool bound to a specific working directory.
    
    Args:
        cwd: Working directory for path resolution
        allowed_dirs: Override allowed directories
        
    Returns:
        A read tool function bound to the specified cwd.
        
    Example:
        read = create_read_tool(cwd="/my/project")
        result = await read("/my/project/src/main.py")
    """
    cwd_path = Path(cwd).resolve()
    effective_allowed = dict(ALLOWED_DIRS)
    if allowed_dirs:
        effective_allowed.update(allowed_dirs)
    # Always allow the cwd
    effective_allowed["cwd"] = cwd_path
    
    def validate_with_cwd(path: str) -> Path | str:
        # Handle relative paths by resolving against cwd
        if not Path(path).is_absolute():
            # Try resolving against cwd first
            candidate = (cwd_path / path).resolve()
            if candidate.exists() or (cwd_path / path).exists():
                abs_path = candidate
            else:
                abs_path = Path(path).expanduser().resolve()
        else:
            abs_path = Path(path).expanduser().resolve()
        
        # Check against allowed dirs
        for _, base in effective_allowed.items():
            if _is_within(abs_path, base):
                return abs_path
        # Check if it's within cwd
        if _is_within(abs_path, cwd_path):
            return abs_path
        return f"Error: Path '{path}' is outside allowed directories"
    
    @tool(name="read", description="Read the contents of a file. Returns the file content or error message.")
    def read_bound(path: str) -> str:
        validated = validate_with_cwd(path)
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
    
    return read_bound


def create_write_tool(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
) -> Callable[[str, str], str]:
    """Create a write tool bound to a specific working directory.
    
    Args:
        cwd: Working directory for path resolution
        allowed_dirs: Override allowed directories
        
    Returns:
        A write tool function bound to the specified cwd.
    """
    cwd_path = Path(cwd).resolve()
    effective_allowed = dict(ALLOWED_DIRS)
    if allowed_dirs:
        effective_allowed.update(allowed_dirs)
    effective_allowed["cwd"] = cwd_path
    
    def validate_with_cwd(path: str) -> Path | str:
        # Handle relative paths by resolving against cwd
        if not Path(path).is_absolute():
            candidate = (cwd_path / path).resolve()
            # For write, we want to allow writing even if file doesn't exist
            # Check if parent directory exists
            if (cwd_path / path).parent.exists():
                abs_path = candidate
            else:
                abs_path = Path(path).expanduser().resolve()
        else:
            abs_path = Path(path).expanduser().resolve()
        
        for _, base in effective_allowed.items():
            if _is_within(abs_path, base):
                return abs_path
        if _is_within(abs_path, cwd_path):
            return abs_path
        return f"Error: Path '{path}' is outside allowed directories"
    
    @tool(name="write", description="Write content to a file. Creates the file if it doesn't exist.")
    def write_bound(path: str, content: str) -> str:
        validated = validate_with_cwd(path)
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
    
    return write_bound


def create_edit_tool(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
) -> Callable[[str, str, str], str]:
    """Create an edit tool bound to a specific working directory.
    
    Args:
        cwd: Working directory for path resolution
        allowed_dirs: Override allowed directories
        
    Returns:
        An edit tool function bound to the specified cwd.
    """
    cwd_path = Path(cwd).resolve()
    effective_allowed = dict(ALLOWED_DIRS)
    if allowed_dirs:
        effective_allowed.update(allowed_dirs)
    effective_allowed["cwd"] = cwd_path
    
    def validate_with_cwd(path: str) -> Path | str:
        abs_path = Path(path).expanduser().resolve()
        for _, base in effective_allowed.items():
            if _is_within(abs_path, base):
                return abs_path
        if _is_within(abs_path, cwd_path):
            return abs_path
        return f"Error: Path '{path}' is outside allowed directories"
    
    @tool(name="edit", description="Edit a file by replacing old_string with new_string. Returns success or error.")
    def edit_bound(path: str, old_string: str, new_string: str) -> str:
        validated = validate_with_cwd(path)
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
    
    return edit_bound


def create_bash_tool(
    cwd: str | Path = ".",
    allowed_commands: list[str] | None = None,
) -> Callable[[str, str | None, int], str]:
    """Create a bash tool bound to a specific working directory.
    
    Args:
        cwd: Working directory for command execution
        allowed_commands: List of allowed command names (if None, uses global ALLOWED_COMMANDS)
        
    Returns:
        A bash tool function bound to the specified cwd.
    """
    cwd_path = Path(cwd).resolve()
    
    @tool(
        name="bash",
        description="Execute a bash command and return the output. WARNING: Use with caution.",
        schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to execute"},
                "cwd": {"type": "string", "description": "Working directory (overrides default)"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        },
    )
    async def bash_bound(command: str, cwd_override: str | None = None, timeout: int = 30) -> str:
        error = _check_dangerous_patterns(command)
        if error:
            return error
        
        # Check against allowed commands if specified
        if allowed_commands is not None:
            tokens = shlex.split(command)
            if tokens:
                base_cmd = tokens[0]
                if base_cmd not in allowed_commands:
                    return f"Error: Command '{base_cmd}' not allowed. Allowed: {', '.join(sorted(allowed_commands))}"
        
        effective_cwd = cwd_override or str(cwd_path)
        
        if timeout > 120:
            return f"Error: Timeout cannot exceed 120 seconds (got {timeout})"

        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=effective_cwd,
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
            return "Error: Permission denied to execute command"
        except Exception as e:
            return f"Error executing command: {e}"
    
    return bash_bound


def create_grep_tool(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
) -> Callable[[str, str, bool, str], str]:
    """Create a grep tool bound to a specific working directory."""
    cwd_path = Path(cwd).resolve()
    effective_allowed = dict(ALLOWED_DIRS)
    if allowed_dirs:
        effective_allowed.update(allowed_dirs)
    effective_allowed["cwd"] = cwd_path
    
    def validate_with_cwd(path: str) -> Path | str:
        abs_path = Path(path).expanduser().resolve()
        for _, base in effective_allowed.items():
            if _is_within(abs_path, base):
                return abs_path
        if _is_within(abs_path, cwd_path):
            return abs_path
        return f"Error: Path '{path}' is outside allowed directories"
    
    @tool(name="grep", description="Search for pattern in files. Returns matching lines with context.")
    def grep_bound(
        pattern: str,
        path: str = ".",
        recursive: bool = True,
        file_pattern: str = "*",
    ) -> str:
        validated = validate_with_cwd(path)
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
    
    return grep_bound


def create_glob_tool(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
) -> Callable[[str, str], str]:
    """Create a glob tool bound to a specific working directory."""
    cwd_path = Path(cwd).resolve()
    effective_allowed = dict(ALLOWED_DIRS)
    if allowed_dirs:
        effective_allowed.update(allowed_dirs)
    effective_allowed["cwd"] = cwd_path
    
    def validate_with_cwd(path: str) -> Path | str:
        abs_path = Path(path).expanduser().resolve()
        for _, base in effective_allowed.items():
            if _is_within(abs_path, base):
                return abs_path
        if _is_within(abs_path, cwd_path):
            return abs_path
        return f"Error: Path '{path}' is outside allowed directories"
    
    @tool(
        name="glob",
        description="Find files matching a glob pattern.",
        schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., '**/*.py')"},
                "path": {"type": "string", "description": "Base directory to search in", "default": "."},
            },
            "required": ["pattern"],
        },
    )
    def glob_bound(pattern: str, path: str = ".") -> str:
        validated = validate_with_cwd(path)
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
    
    return glob_bound


def create_core_tools(
    cwd: str | Path = ".",
    allowed_dirs: dict[str, Path] | None = None,
    allowed_commands: list[str] | None = None,
) -> list[Callable]:
    """Create all core tools bound to a specific working directory.
    
    Args:
        cwd: Working directory for file operations and bash
        allowed_dirs: Override allowed directories for file operations
        allowed_commands: List of allowed bash commands
        
    Returns:
        List of core tool functions bound to the specified cwd.
        
    Example:
        tools = create_core_tools(cwd="/my/project")
        agent = Agent(tools=tools)
    """
    return [
        create_read_tool(cwd=cwd, allowed_dirs=allowed_dirs),
        create_write_tool(cwd=cwd, allowed_dirs=allowed_dirs),
        create_edit_tool(cwd=cwd, allowed_dirs=allowed_dirs),
        create_bash_tool(cwd=cwd, allowed_commands=allowed_commands),
        create_grep_tool(cwd=cwd, allowed_dirs=allowed_dirs),
        create_glob_tool(cwd=cwd, allowed_dirs=allowed_dirs),
    ]


# =============================================================================
# Default Tools (use global ALLOWED_DIRS with Path.cwd())
# =============================================================================

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
        return "Error: Permission denied to execute command"
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
