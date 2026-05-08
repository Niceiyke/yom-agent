"""Built-in GitHub API tool for yom."""

from __future__ import annotations

import json

from yom.tools import tool


@tool(
    name="github_api",
    description="""Make a GitHub API request.
    
    Args:
        endpoint: GitHub API endpoint (e.g., /repos/octocat/Hello-World)
        method: HTTP method (GET, POST, PUT, DELETE)
        body: Request body as JSON string
        token: GitHub personal access token (or set GITHUB_TOKEN env var)
    
    Returns:
        GitHub API response as JSON.
    """,
    schema={
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "GitHub API endpoint (e.g., /user, /repos/owner/repo)"
            },
            "method": {
                "type": "string",
                "description": "HTTP method",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "default": "GET"
            },
            "body": {
                "type": "string",
                "description": "Request body as JSON string"
            },
            "token": {
                "type": "string",
                "description": "GitHub personal access token"
            }
        },
        "required": ["endpoint"]
    }
)
def github_api(
    endpoint: str,
    method: str = "GET",
    body: str | None = None,
    token: str | None = None,
) -> str:
    """Make a GitHub API request."""
    import os

    import httpx

    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        return "Error: GitHub token required. Set GITHUB_TOKEN env var or pass token parameter."

    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        client = httpx.Client(timeout=30.0)
        
        if body and method in ("POST", "PUT", "PATCH"):
            response = client.request(method, url, headers=headers, json=json.loads(body))
        else:
            response = client.request(method, url, headers=headers)
        
        client.close()
        
        try:
            return json.dumps(response.json(), indent=2, default=str)
        except Exception:
            return f"Status: {response.status_code}\n{response.text}"

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


@tool(
    name="github_read_file",
    description="""Read a file from a GitHub repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        path: File path in repository
        ref: Branch, tag, or commit SHA
        token: GitHub personal access token
    
    Returns:
        File content.
    """,
    schema={
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "path": {"type": "string", "description": "File path in repository"},
            "ref": {"type": "string", "description": "Branch or commit SHA"},
            "token": {"type": "string", "description": "GitHub token"}
        },
        "required": ["owner", "repo", "path"]
    }
)
def github_read_file(
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
    token: str | None = None,
) -> str:
    """Read a file from GitHub repository."""
    
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"
    if ref:
        endpoint += f"?ref={ref}"
    
    result = github_api(endpoint=endpoint, token=token)
    
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "content" in data:
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content
        return result
    except Exception:
        return result


@tool(
    name="github_search",
    description="""Search GitHub for repositories, code, or issues.
    
    Args:
        query: Search query (e.g., "language:python stars:>1000")
        search_type: Type of search (repositories, code, issues)
        token: GitHub personal access token
    
    Returns:
        Search results.
    """,
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "search_type": {
                "type": "string",
                "description": "Type of search",
                "enum": ["repositories", "code", "issues"],
                "default": "repositories"
            },
            "token": {"type": "string", "description": "GitHub token"}
        },
        "required": ["query"]
    }
)
def github_search(
    query: str,
    search_type: str = "repositories",
    token: str | None = None,
) -> str:
    """Search GitHub."""
    endpoint = f"/search/{search_type}?q={query}&per_page=10"
    return github_api(endpoint=endpoint, token=token)


__all__ = ["github_api", "github_read_file", "github_search"]
