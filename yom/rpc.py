"""Minimal JSON-RPC 2.0 types for yom."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request."""

    method: str
    params: dict[str, Any] | list[Any] | None = None
    id: str | int | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            data["params"] = self.params
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass
class JSONRPCError:
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        data = {"code": int(self.code), "message": self.message}
        if self.data is not None:
            data["data"] = self.data
        return data


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response."""

    id: str | int | None = None
    result: Any = None
    error: JSONRPCError | dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            data["error"] = self.error.to_dict() if hasattr(self.error, "to_dict") else self.error
        else:
            data["result"] = self.result
        return data


def success_response(id: str | int | None, result: Any) -> JSONRPCResponse:
    """Create a JSON-RPC success response."""
    return JSONRPCResponse(id=id, result=result)


def error_response(
    id: str | int | None,
    code: ErrorCode | int,
    message: str,
    data: Any = None,
) -> JSONRPCResponse:
    """Create a JSON-RPC error response."""
    return JSONRPCResponse(id=id, error=JSONRPCError(code=int(code), message=message, data=data))


__all__ = [
    "ErrorCode",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "success_response",
    "error_response",
]
