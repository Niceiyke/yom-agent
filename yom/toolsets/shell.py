"""Built-in shell tool for yom with enhanced security."""

from __future__ import annotations

import shlex

from yom.tools import tool


# Whitelist of safe commands
SAFE_COMMANDS = {
    "ls", "dir", "cat", "head", "tail", "grep", "find", "pwd", "cd",
    "echo", "printf", "wc", "sort", "uniq", "awk", "sed", "cut", "tr",
    "jq", "curl", "wget", "git", "docker", "docker-compose", "kubectl",
    "helm", "terraform", "ansible", "make", "cmake", "npm", "yarn", "pnpm",
    "pip", "pip3", "poetry", "uv", "python", "python3", "node", "npm",
    "go", "cargo", "rustc", "java", "javac", "ruby", "php", "perl",
    "rsync", "scp", "ssh", "ftp", "sftp", "tar", "zip", "unzip",
    "gzip", "gunzip", "bzip2", "xz", "md5sum", "sha256sum", "sha1sum",
    "base64", "xxd", "hexdump", "od", "strings", "file", "stat",
    "lsblk", "df", "du", "free", "top", "ps", "kill", "pgrep",
    "which", "whereis", "type", "command", "env", "export", "printenv",
    "date", "cal", "uptime", "hostname", "id", "whoami", "groups",
    "chmod", "chown", "chgrp", "touch", "mkdir", "rmdir", "cp", "mv", "rm",
    "ln", "readlink", "realpath", "dirname", "basename", "mktemp",
}


@tool(
    name="shell",
    description="""Execute a shell command with safety checks.
    
    Args:
        command: The shell command to execute
        cwd: Working directory
        timeout: Timeout in seconds (max: 300)
        allow_sudo: Allow sudo (default: false)
    
    Returns:
        Command output or error.
    """,
    schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "cwd": {"type": "string", "description": "Working directory"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60},
            "allow_sudo": {"type": "boolean", "description": "Allow sudo commands", "default": False}
        },
        "required": ["command"]
    }
)
def shell(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    allow_sudo: bool = False,
) -> str:
    """Execute a shell command with safety checks."""
    import asyncio
    import re

    # Check for dangerous patterns
    dangerous_patterns = [
        (r"\|\s*rm\s+-rf", "Pipeline to rm -rf is dangerous"),
        (r";\s*rm\s+-rf", "Chained rm -rf is dangerous"),
        (r"&\s*rm\s+-rf", "Background rm -rf is dangerous"),
        (r"rm\s+-rf\s+/", "Cannot delete root filesystem"),
        (r">\s*/dev/sd", "Cannot write directly to disk device"),
        (r"dd\s+if=.*of=/dev/", "Cannot write directly to disk device"),
        (r":()\s*{\s*:|:\s*&\s*:\s*\|:\s*&\s*;}\s*:\s*$", "Fork bomb detected"),
        (r"curl.*\|\s*sh", "Piping curl to shell is dangerous"),
        (r"wget.*\|\s*sh", "Piping wget to shell is dangerous"),
        (r"base64\s+-d.*\|.*sh", "Decoding and piping to shell is dangerous"),
    ]

    for pattern, reason in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Error: Dangerous pattern detected - {reason}"

    # Check for sudo
    if not allow_sudo and re.search(r"\bsudo\b", command):
        return "Error: sudo not allowed. Set allow_sudo=true to enable."

    # Validate command is in whitelist or explicitly allowed
    tokens = shlex.split(command)
    if tokens:
        base_cmd = tokens[0]
        if base_cmd not in SAFE_COMMANDS and not allow_sudo:
            return f"Error: Command '{base_cmd}' not in whitelist. Allowlist: {', '.join(sorted(SAFE_COMMANDS))}"

    # Limit timeout
    if timeout > 300:
        return f"Error: Timeout cannot exceed 300 seconds (got {timeout})"

    if timeout < 1:
        return f"Error: Timeout must be at least 1 second"

    async def run():
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            output = stdout.decode(errors="replace") if stdout else ""
            err = stderr.decode(errors="replace") if stderr else ""
            
            if process.returncode != 0:
                return f"[Exit code: {process.returncode}]\n{err or output}"
            return output or "[No output]"
            
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout} seconds"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    return asyncio.run(run())


@tool(
    name="shell_script",
    description="""Execute a shell script from a file.
    
    Args:
        script_path: Path to the script file
        args: Arguments to pass to the script
        cwd: Working directory
        timeout: Timeout in seconds
    
    Returns:
        Script output or error.
    """,
    schema={
        "type": "object",
        "properties": {
            "script_path": {"type": "string", "description": "Path to script file"},
            "args": {"type": "string", "description": "Script arguments"},
            "cwd": {"type": "string", "description": "Working directory"},
            "timeout": {"type": "integer", "description": "Timeout", "default": 60}
        },
        "required": ["script_path"]
    }
)
def shell_script(
    script_path: str,
    args: str = "",
    cwd: str | None = None,
    timeout: int = 60,
) -> str:
    """Execute a shell script."""
    import os
    from pathlib import Path

    path = Path(script_path).resolve()
    
    if not path.exists():
        return f"Error: Script not found: {script_path}"
    
    if not os.access(path, os.R_OK):
        return f"Error: Script not readable: {script_path}"
    
    # Check shebang
    with open(path) as f:
        first_line = f.readline()
    
    allowed_shebang = {"#!/bin/bash", "#!/bin/sh", "#!/usr/bin/env bash", "#!/usr/bin/env sh"}
    if not any(first_line.startswith(s) for s in allowed_shebang):
        return f"Error: Unsupported shebang. Allowed: {', '.join(allowed_shebang)}"
    
    cmd = f"bash {shlex.quote(str(path))}"
    if args:
        cmd += f" {args}"
    
    return shell(command=cmd, cwd=cwd, timeout=timeout)


__all__ = ["shell", "shell_script"]
