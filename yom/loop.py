"""Standalone agent loop with tool calling."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from yom.models import AgentState, Message as YomMessage
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
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arguments": self.arguments,
        }


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

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get tool schemas for LLM."""
        schemas = []
        for tool in self.tools:
            name = getattr(tool, "_tool_name", None) or getattr(tool, "name", None)
            if not name:
                continue
            desc = getattr(tool, "_tool_description", "") or getattr(tool, "description", "")
            params = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", {}) or {}

            schema = {
                "name": name,
                "description": desc,
                "parameters": params if "properties" in params else {"properties": params, "type": "object"},
            }
            schemas.append(schema)
        return schemas

    def _parse_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """Parse tool calls from LLM response content."""
        tool_calls = []

        # Handle content that might be JSON with tool calls
        content = response.content

        # Try to find tool call JSON in content
        # Pattern: tool-use blocks in Anthropic format or similar
        try:
            # If content is a dict or has structured data
            if isinstance(content, dict):
                pass
            # Try to find JSON array of tool calls
            json_match = re.search(r'\[.*?\{.*?\}.*?\]', content, re.DOTALL)
            if json_match:
                tool_data = json.loads(json_match.group())
                if isinstance(tool_data, list):
                    for item in tool_data:
                        if isinstance(item, dict) and "name" in item:
                            tool_calls.append(ToolCall(
                                name=item["name"],
                                arguments=item.get("arguments", item.get("input", {})),
                            ))
        except (json.JSONDecodeError, TypeError):
            pass

        return tool_calls

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
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
            execute_fn = tool

        # Execute
        try:
            result = execute_fn(**tool_call.arguments)
            if asyncio.iscoroutine(result):
                result = asyncio.run(result)
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

        # Convert yom messages to provider messages
        provider_messages = self._convert_messages(messages)

        # Add system prompt with tool schemas
        system_content = "You are a helpful assistant with access to tools."
        tool_schemas = self._get_tool_schemas()
        if tool_schemas:
            system_content += "\n\nWhen you need to use a tool, respond with JSON:\n"
            system_content += json.dumps({"tool_calls": [{"name": "tool_name", "arguments": {}}]})
            system_content += "\n\nAvailable tools:\n" + json.dumps(tool_schemas, indent=2)

        # Add system message
        provider_messages.insert(0, Message(role="system", content=system_content))

        iteration = 0
        total_tool_calls = 0

        while iteration < max_turns:
            iteration += 1

            # Call LLM
            response = await self.provider.complete(provider_messages, model, config)

            # Check for tool calls in response
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # No tool calls, return text response
                return response.content, [], total_tool_calls

            # Execute tools
            tool_results = []
            for tc in tool_calls[:self.config.max_tool_calls]:
                result = self._execute_tool(tc)
                tool_results.append(result)
                total_tool_calls += 1

            # Add assistant message with tool calls
            assistant_msg = Message(
                role="assistant",
                content=response.content,
            )
            provider_messages.append(assistant_msg)

            # Add tool results as tool messages
            for result in tool_results:
                tool_msg = Message(
                    role="tool",
                    content=json.dumps({"name": result.name, "result": result.content, "error": result.error}),
                )
                provider_messages.append(tool_msg)

        # Max turns reached
        return f"Max turns ({max_turns}) reached. Last response: {response.content}", [], total_tool_calls

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