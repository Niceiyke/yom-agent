"""Built-in HTTP client tool for yom."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from yom.tools import tool


@dataclass
class HttpResponse:
    """HTTP response container."""
    status_code: int
    headers: dict[str, str]
    body: str
    is_json: bool = False
    json_data: Any = None


def _parse_headers(headers: Any) -> dict[str, str]:
    """Parse httpx headers to dict."""
    if hasattr(headers, "items"):
        return {k.lower(): v for k, v in headers.items()}
    # Fallback for list of tuples
    return {str(k).lower(): str(v) for k, v in headers}


@tool(
    name="http_request",
    description="""Make an HTTP request. Supports GET, POST, PUT, DELETE methods.
    
    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        headers: Optional headers as JSON string
        body: Optional request body as JSON string
        timeout: Request timeout in seconds (default: 30)
    
    Returns:
        Status code, headers, and body of the response.
    """,
    schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to request"
            },
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                "default": "GET"
            },
            "headers": {
                "type": "string",
                "description": "Headers as JSON string (e.g., '{\"Authorization\": \"Bearer token\"}')"
            },
            "body": {
                "type": "string",
                "description": "Request body as JSON string"
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds",
                "default": 30
            }
        },
        "required": ["url"]
    }
)
def http_request(
    url: str,
    method: str = "GET",
    headers: str | None = None,
    body: str | None = None,
    timeout: int = 30,
) -> str:
    """Make an HTTP request (sync wrapper for backward compatibility).
    
    For async execution with parallel requests, use http_request_async.
    """

    import httpx

    try:
        header_dict = {}
        if headers:
            try:
                header_dict = json.loads(headers)
            except json.JSONDecodeError:
                return f"Error: Invalid headers JSON: {headers}"

        request_body = None
        if body and method in ("POST", "PUT", "PATCH"):
            try:
                request_body = json.loads(body)
            except json.JSONDecodeError:
                request_body = body

        response = httpx.request(
            method=method,
            url=url,
            headers=header_dict,
            json=request_body if isinstance(request_body, dict) else None,
            data=request_body if isinstance(request_body, str) else {},
            timeout=timeout,
        )

        response_headers = _parse_headers(response.headers)

        try:
            response_json = response.json()
            is_json = True
            body_content = json.dumps(response_json, indent=2)
        except (json.JSONDecodeError, Exception):
            is_json = False
            body_content = response.text

        return json.dumps({
            "status_code": response.status_code,
            "headers": response_headers,
            "is_json": is_json,
            "body": body_content,
            "url": url,
        })

    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout}s"
    except httpx.ConnectError as e:
        return f"Error: Connection failed: {e}"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"


@tool(
    name="get_json",
    description="""Fetch JSON data from a URL and parse it.
    
    Args:
        url: The URL to fetch JSON from
        headers: Optional headers as JSON string
    
    Returns:
        Parsed JSON data as formatted string.
    """,
    schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch JSON from"
            },
            "headers": {
                "type": "string",
                "description": "Optional headers as JSON string"
            }
        },
        "required": ["url"]
    }
)
def get_json(url: str, headers: str | None = None) -> str:
    """Fetch and parse JSON from URL."""
    result = http_request(url=url, method="GET", headers=headers)
    
    try:
        data = json.loads(result)
        if data.get("is_json") and data.get("body"):
            return data["body"]
        return result
    except Exception:
        return result


__all__ = ["http_request", "get_json"]
