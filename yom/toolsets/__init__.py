"""Built-in toolsets for yom-agent.

Toolsets provide specialized tools for common tasks:
- http: HTTP client tools
- database: SQL query and schema tools  
- github: GitHub API tools
- storage: S3-compatible storage tools
- shell: Secure shell command execution

Usage:
    from yom.toolsets import http, database, github, storage, shell
    from yom import Agent

    agent = Agent(tools=["core", http, database, github])
"""

from yom.toolsets.http import http_request, get_json
from yom.toolsets.database import query_db, db_schema
from yom.toolsets.github import github_api, github_read_file, github_search
from yom.toolsets.storage import s3_put, s3_get, s3_list
from yom.toolsets.shell import shell, shell_script
from yom.toolsets.telegram import TelegramBot, telegram_send

__all__ = [
    # HTTP tools
    "http_request",
    "get_json",
    # Database tools
    "query_db",
    "db_schema",
    # GitHub tools
    "github_api",
    "github_read_file",
    "github_search",
    # Storage tools
    "s3_put",
    "s3_get",
    "s3_list",
    # Shell tools
    "shell",
    "shell_script",
    # Telegram tools
    "TelegramBot",
    "telegram_send",
]
