"""Standalone agent loop with tool calling."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from yom.models import Message as YomMessage
from yom.providers import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    create_provider,
)
from yom.tools import Tool


@dataclass
class ToolCall:
    """A tool call request from the LLM."""
    id: str | None = None
    tool_call_id: str | None = None
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "arguments": self.arguments,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass
class ToolResult:
    """Result from executing a tool."""
    name: str
    content: str
    error: str | None = None


@dataclass
class AgentLoopConfig:
    """Configuration for the agent loop."""
    max_turns: int = 50
    max_tool_calls: int = 20
    tool_call_timeout: float = 30.0
    truncate_messages: bool = False
    max_context_tokens: int | None = None


class AgentLoop:
    """Agent loop that handles turn execution with tool calling."""

    def __init__(
        self,
        provider: BaseProvider,
        tools: list[Tool] | None = None,
        config: AgentLoopConfig | None = None,
    ):
        self.provider = provider
        self.tools = tools or []
        self.config = config or AgentLoopConfig()
        self._last_usage: dict | None = None

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get tool schemas for LLM in provider-agnostic format."""
        schemas = []
        for tool in self.tools:
            name = getattr(tool, "_tool_name", None) or getattr(tool, "name", None)
            if not name:
                continue
            desc = getattr(tool, "_tool_description", None) or getattr(tool, "description", None) or ""
            # Ensure description is a string (avoid MagicMock issues)
            if not isinstance(desc, str):
                desc = str(desc) if desc else ""
            params = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", None) or {}

            # Normalize schema format for different providers
            if isinstance(params, dict):
                if "properties" not in params:
                    params = {"type": "object", "properties": params}
            else:
                params = {"type": "object", "properties": {}}

            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
            schemas.append(schema)
        return schemas

    def _parse_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """Parse tool calls from LLM response content."""
        tool_calls = []

        # Handle structured responses from providers
        raw = response.raw or {}
        content = response.content if isinstance(response.content, str) else ""

        # Check for provider-specific tool_call structures first
        # OpenAI format: response.raw might contain tool_calls
        if "tool_calls" in raw:
            for tc in raw.get("tool_calls", []):
                if isinstance(tc, dict):
                    func = tc.get("function", tc)
                    args = func.get("arguments", {})
                    # Arguments may be a JSON string, parse if needed
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    tool_calls.append(ToolCall(
                        tool_call_id=tc.get("id"),
                        name=func.get("name", ""),
                        arguments=args,
                    ))
            return tool_calls

        # Anthropic format: response.raw might have content blocks with input
        if "content" in raw:
            content_blocks = raw.get("content", [])
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_calls.append(ToolCall(
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        ))
                if tool_calls:
                    return tool_calls

        # Fallback: parse from text content
        # Try to find and parse tool_calls JSON array
        patterns = [
            r'"tool_calls"\s*:\s*(\[[^\]]*\])',
            r'tool_calls\s*\|\s*(\[.*?\])',
        ]

        for pattern in patterns:
            try:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    json_str = match.group(1) if '(' in pattern else match.group(0)
                    data = json.loads(json_str)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "name" in item:
                                args = item.get("arguments", item.get("input", {}))
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except json.JSONDecodeError:
                                        args = {"value": args}
                                tool_calls.append(ToolCall(
                                    name=item["name"],
                                    arguments=args,
                                ))
                        if tool_calls:
                            break
            except (json.JSONDecodeError, TypeError, re.error):
                continue

        # Last resort: look for name/arguments pairs in content
        if not tool_calls:
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', content)
            args_match = re.search(r'"arguments"\s*:\s*(\{[^}]+\})', content)
            if name_match and args_match:
                try:
                    args = json.loads(args_match.group(1))
                    tool_calls.append(ToolCall(name=name_match.group(1), arguments=args))
                except json.JSONDecodeError:
                    pass

        return tool_calls

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool and return result."""
        tool_name = tool_call.name

        # Find the tool
        tool = None
        for t in self.tools:
            name = getattr(t, "_tool_name", None) or getattr(t, "name", None)
            if name == tool_name:
                tool = t
                break

        if tool is None:
            return ToolResult(
                name=tool_name,
                content="",
                error=f"unknown_tool: {tool_name}",
            )

        # Get execute function
        execute_fn = getattr(tool, "execute", None)
        if execute_fn is None:
            execute_fn = tool  # type: ignore[assignment]

        # Execute
        try:
            result = execute_fn(**tool_call.arguments)  # type: ignore[operator]
            if asyncio.iscoroutine(result):
                result = await result
            if hasattr(result, "content"):
                return ToolResult(name=tool_name, content=result.content)
            return ToolResult(name=tool_name, content=str(result))
        except Exception as e:
            return ToolResult(name=tool_name, content="", error=f"tool_error: {e}")

    async def run_turn(
        self,
        messages: list[YomMessage],
        model: str,
        config: CompletionConfig | None = None,
        max_turns: int | None = None,
    ) -> tuple[str, list[ToolCall], int]:
        """Run a single turn with tool calling.

        Returns:
            (final_text, tool_calls_made, tool_calls_count)
        """
        if not messages:
            return "No messages to process", [], 0

        max_turns = max_turns or self.config.max_turns
        config = config or CompletionConfig(max_tokens=4096)

        provider_messages = self._convert_messages(messages)

        tool_schemas = self._get_tool_schemas()
        if tool_schemas:
            system_content = "You are a helpful assistant with access to tools. Use them as needed."
            provider_messages.insert(0, Message(role="system", content=system_content))
        else:
            system_content = "You are a helpful assistant."
            provider_messages.insert(0, Message(role="system", content=system_content))

        iteration = 0
        total_tool_calls = 0
        all_tool_calls: list[ToolCall] = []

        while iteration < max_turns:
            iteration += 1

            response = await self.provider.complete(provider_messages, model, config, tools=tool_schemas if tool_schemas else None)

            if response.usage:
                self._last_usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                return response.content, all_tool_calls, total_tool_calls

            tool_results = []
            for tc in tool_calls[:self.config.max_tool_calls]:
                result = await self._execute_tool(tc)
                tool_results.append(result)
                total_tool_calls += 1
                all_tool_calls.append(tc)

            assistant_msg = Message(
                role="assistant",
                content=response.content,
            )
            provider_messages.append(assistant_msg)

            # Add tool_calls to assistant message if there were tool calls
            if all_tool_calls:
                tc_list = []
                for tc in all_tool_calls:
                    args = tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments)
                    tc_list.append({
                        "id": tc.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": args,
                        }
                    })
                # Store tool_calls info for convert_messages to include
                assistant_msg.metadata["_tool_calls"] = tc_list

            for result, tc in zip(tool_results, tool_calls):
                tool_msg = Message(
                    role="tool",
                    content=json.dumps({"name": result.name, "result": result.content, "error": result.error}),
                    tool_call_id=tc.tool_call_id,
                    name=result.name,
                )
                provider_messages.append(tool_msg)

        return f"Max turns ({max_turns}) reached. Last response: {response.content}", all_tool_calls, total_tool_calls

    def _convert_messages(self, yom_messages: list[YomMessage]) -> list[Message]:
        """Convert yom messages to provider messages."""
        result = []
        for msg in yom_messages:
            if hasattr(msg, 'content'):
                content = msg.content
            else:
                content = str(msg)
            role = getattr(msg, 'role', 'user')
            if hasattr(role, 'value'):
                role = role.value
            result.append(Message(role=role, content=content))
        return result

    async def stream_turn(
        self,
        messages: list[YomMessage],
        model: str,
        config: CompletionConfig | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a turn response."""
        if not messages:
            yield StreamChunk(content="No messages to process", is_final=True)
            return

        provider_messages = self._convert_messages(messages)

        system_content = "You are a helpful assistant."
        tool_schemas = self._get_tool_schemas()
        if tool_schemas:
            system_content += " Use tools when needed."

        provider_messages.insert(0, Message(role="system", content=system_content))

        config = config or CompletionConfig(max_tokens=4096)

        async for chunk in self.provider.stream(provider_messages, model, config):
            yield chunk

        yield StreamChunk(content="", is_final=True)


def create_agent_loop(
    model: str,
    provider: BaseProvider | None = None,
    tools: list[Tool] | None = None,
    config: AgentLoopConfig | None = None,
) -> AgentLoop:
    """Create an agent loop with provider auto-detection."""
    if provider is None:
        provider = create_provider(model=model)
    return AgentLoop(provider=provider, tools=tools, config=config)