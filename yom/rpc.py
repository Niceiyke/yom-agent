"""RPC mode for yom - JSON-RPC over stdin/stdout.

This enables yom to be used as a subprocess from any language.

Usage:
    # Server mode (run yom as subprocess)
    yom --mode rpc
    
    # Or programmatically:
    from yom.rpc import serve_rpc
    await serve_rpc()
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4


# JSON-RPC 2.0 message types
@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request."""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str = ""
    params: dict[str, Any] | list | None = None

    def to_dict(self) -> dict:
        result = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            result["id"] = self.id
        if self.params is not None:
            result["params"] = self.params
        return result

    @classmethod
    def from_dict(cls, data: dict) -> JSONRPCRequest:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params"),
        )


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response."""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        result = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            result["id"] = self.id
        if self.error is not None:
            result["error"] = self.error
        elif self.result is not None:
            result["result"] = self.result
        return result


def error_response(id: str | int | None, code: int, message: str, data: Any = None) -> JSONRPCResponse:
    """Create an error response."""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONRPCResponse(id=id, error=error)


# Error codes
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


# Method handlers
_method_handlers: dict[str, Callable[..., Any]] = {}


def register_method(name: str, handler: Callable[..., Any]) -> None:
    """Register an RPC method handler.
    
    Args:
        name: Method name (e.g., "agent.run")
        handler: Async function that takes params dict and returns result
    """
    _method_handlers[name] = handler


async def handle_request(request: JSONRPCRequest) -> JSONRPCResponse:
    """Handle a JSON-RPC request."""
    if request.jsonrpc != "2.0":
        return error_response(
            request.id,
            ErrorCode.INVALID_REQUEST,
            "Invalid JSON-RPC version"
        )
    
    method = request.method
    if not method:
        return error_response(
            request.id,
            ErrorCode.INVALID_REQUEST,
            "Method name required"
        )
    
    # Check for built-in methods
    if method == "rpc.discover":
        return JSONRPCResponse(
            id=request.id,
            result={"methods": list(_method_handlers.keys())}
        )
    
    handler = _method_handlers.get(method)
    if handler is None:
        return error_response(
            request.id,
            ErrorCode.METHOD_NOT_FOUND,
            f"Method not found: {method}"
        )
    
    try:
        result = handler(request.params or {})
        if asyncio.iscoroutine(result):
            result = await result
        return JSONRPCResponse(id=request.id, result=result)
    except TypeError as e:
        return error_response(request.id, ErrorCode.INVALID_PARAMS, str(e))
    except Exception as e:
        return error_response(request.id, ErrorCode.INTERNAL_ERROR, str(e))


async def read_messages() -> AsyncIterator[JSONRPCRequest]:
    """Read JSON-RPC requests from stdin.
    
    Messages are newline-delimited JSON (JSONL).
    """
    loop = asyncio.get_event_loop()
    
    while True:
        line = await loop.run_in_executor(sys.stdin, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            yield JSONRPCRequest.from_dict(data)
        except json.JSONDecodeError:
            yield JSONRPCRequest(id=None, error={"code": ErrorCode.PARSE_ERROR, "message": "Invalid JSON"})


async def write_message(response: JSONRPCResponse) -> None:
    """Write a JSON-RPC response to stdout."""
    line = json.dumps(response.to_dict())
    print(line, flush=True)


async def serve_rpc(
    agent_factory: Callable[..., Any] | None = None,
) -> None:
    """Start the RPC server.
    
    Reads JSON-RPC requests from stdin and writes responses to stdout.
    
    Args:
        agent_factory: Optional callable that returns an Agent instance.
                      If None, a default agent is created.
    
    Supported methods:
        - agent.run: Run a prompt
        - agent.call_tool: Call a tool directly
        - agent.get_state: Get current agent state
        - agent.abort: Abort current operation
        - agent.subscribe: Subscribe to events
        - agent.get_session_messages: Get session messages
        - rpc.discover: List available methods
    """
    from yom import Agent, AgentState
    
    # Create default agent if no factory provided
    _agent = None
    
    def get_agent() -> Agent:
        nonlocal _agent
        if _agent is None:
            _agent = Agent()
        return _agent
    
    # Register method handlers
    async def agent_run(params: dict) -> dict:
        prompt = params.get("prompt", "")
        stream = params.get("stream", False)
        agent = get_agent()
        result = await agent.run(prompt, stream=stream)
        return {"content": result}
    
    async def agent_call_tool(params: dict) -> dict:
        name = params.get("name", "")
        args = params.get("args", {})
        agent = get_agent()
        result = await agent.call_tool(name, args)
        return {"result": result}
    
    async def agent_get_state(params: dict) -> dict:
        agent = get_agent()
        state = agent.state
        if state is None:
            return {"state": None}
        return {
            "state": {
                "session_id": state.session_id,
                "runtime_id": state.runtime_id,
                "current_turn": state.current_turn,
                "message_count": len(state.messages),
            }
        }
    
    async def agent_abort(params: dict) -> dict:
        reason = params.get("reason")
        agent = get_agent()
        agent.abort(reason)
        return {"aborted": True}
    
    async def agent_get_messages(params: dict) -> dict:
        agent = get_agent()
        messages = await agent.get_session_messages()
        return {"messages": messages}
    
    async def agent_new_session(params: dict) -> dict:
        agent = get_agent()
        agent.clear_session()
        return {"session_id": agent.session_id}
    
    async def agent_dispose(params: dict) -> dict:
        agent = get_agent()
        await agent.dispose()
        return {"disposed": True}
    
    # Register handlers
    register_method("agent.run", agent_run)
    register_method("agent.call_tool", agent_call_tool)
    register_method("agent.get_state", agent_get_state)
    register_method("agent.abort", agent_abort)
    register_method("agent.get_session_messages", agent_get_messages)
    register_method("agent.new_session", agent_new_session)
    register_method("agent.dispose", agent_dispose)
    
    # Main RPC loop
    try:
        async for request in read_messages():
            response = await handle_request(request)
            await write_message(response)
    except KeyboardInterrupt:
        pass
    finally:
        # Cleanup
        if _agent is not None:
            await _agent.dispose()


class RPCClient:
    """Client for connecting to a yom RPC server.
    
    Example:
        client = RPCClient()  # Connects to yom --mode rpc via stdin/stdout
        
        # Run a prompt
        result = await client.call("agent.run", {"prompt": "Hello"})
        print(result["content"])
        
        # Call a tool
        result = await client.call("agent.call_tool", {"name": "read", "args": {"path": "/tmp/test.txt"}})
        
        # Cleanup
        await client.close()
    """
    
    def __init__(self, input_stream=None, output_stream=None):
        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout
        self._request_id = 0
        self._pending: dict[str | int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._closed = False
    
    async def _read_responses(self) -> None:
        """Read responses from the server in a background task."""
        loop = asyncio.get_event_loop()
        
        while not self._closed:
            line = await loop.run_in_executor(self._input, self._input.readline)
            if not line:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                response = JSONRPCResponse(**data)
                
                if response.id is not None and response.id in self._pending:
                    future = self._pending.pop(response.id)
                    if response.error:
                        future.set_exception(Exception(response.error.get("message", "Unknown error")))
                    else:
                        future.set_result(response.result)
            except Exception as e:
                # Log but don't crash
                print(f"Error reading response: {e}", file=sys.stderr)
    
    async def call(self, method: str, params: dict | None = None) -> Any:
        """Call an RPC method.
        
        Args:
            method: Method name
            params: Method parameters
            
        Returns:
            Method result
            
        Raises:
            Exception if the server returns an error
        """
        if self._closed:
            raise RuntimeError("Client is closed")
        
        self._request_id += 1
        req_id = self._request_id
        
        request = JSONRPCRequest(
            id=req_id,
            method=method,
            params=params or {}
        )
        
        # Start reader if not started
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(self._read_responses())
        
        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        
        # Send request
        line = json.dumps(request.to_dict())
        self._output.write(line + "\n")
        self._output.flush()
        
        # Wait for response
        return await future
    
    async def close(self) -> None:
        """Close the client connection."""
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass


async def create_rpc_client() -> RPCClient:
    """Create an RPC client connected to stdin/stdout.
    
    Returns:
        RPCClient instance
    """
    client = RPCClient()
    return client


def main():
    """Entry point for RPC mode."""
    asyncio.run(serve_rpc())


if __name__ == "__main__":
    main()
