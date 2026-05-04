"""Tests for agent loop."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from yom.loop import AgentLoop, AgentLoopConfig, ToolCall, ToolResult, create_agent_loop
from yom.providers.base import CompletionConfig, LLMResponse, Message


class TestAgentLoopConfig:
    """Tests for AgentLoopConfig."""

    def test_default_values(self):
        """Test default configuration."""
        config = AgentLoopConfig()
        assert config.max_turns == 50
        assert config.max_tool_calls == 20
        assert config.truncate_messages is False
        assert config.max_context_tokens is None

    def test_custom_values(self):
        """Test custom configuration."""
        config = AgentLoopConfig(
            max_turns=10,
            max_tool_calls=5,
            truncate_messages=True,
            max_context_tokens=4000,
        )
        assert config.max_turns == 10
        assert config.max_tool_calls == 5
        assert config.truncate_messages is True
        assert config.max_context_tokens == 4000


class TestAgentLoop:
    """Tests for AgentLoop."""

    @pytest.mark.asyncio
    async def test_run_turn_no_messages(self):
        """Test run_turn with empty messages."""
        mock_provider = MagicMock()
        loop = AgentLoop(provider=mock_provider)

        result, tool_calls, count = await loop.run_turn([], "gpt-4")
        assert result == "No messages to process"
        assert tool_calls == []
        assert count == 0

    @pytest.mark.asyncio
    async def test_run_turn_no_tool_calls(self):
        """Test run_turn when LLM returns no tool calls."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=LLMResponse(
            content="Hello!",
            model="gpt-4",
        ))

        loop = AgentLoop(provider=mock_provider)
        messages = [Message(role="user", content="Hi")]

        result, tool_calls, count = await loop.run_turn(messages, "gpt-4")
        assert result == "Hello!"
        assert tool_calls == []
        assert count == 0

    @pytest.mark.asyncio
    async def test_run_turn_enforces_max_turns(self):
        """Test that max_turns is enforced."""
        mock_provider = MagicMock()

        async def mock_complete(messages, model, config=None, tools=None):
            return LLMResponse(
                content='{"tool_calls": [{"name": "read", "arguments": {"path": "a.txt"}}]}',
                model=model,
            )

        mock_provider.complete = AsyncMock(side_effect=mock_complete)

        config = AgentLoopConfig(max_turns=3)
        loop = AgentLoop(provider=mock_provider, config=config)
        messages = [Message(role="user", content="Hi")]

        result, tool_calls, count = await loop.run_turn(messages, "gpt-4")

        assert "Max turns" in result
        assert mock_provider.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_run_turn_tool_execution(self):
        """Test tool calling in run_turn."""
        mock_provider = MagicMock()

        call_count = 0

        async def mock_complete(messages, model, config=None, tools=None):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return LLMResponse(
                    content='{"tool_calls": [{"name": "read", "arguments": {"path": "a.txt"}}]}',
                    model=model,
                )
            return LLMResponse(content="File contents: hello", model=model)

        mock_provider.complete = AsyncMock(side_effect=mock_complete)

        mock_read = MagicMock()
        mock_read._tool_name = "read"
        mock_read.execute = MagicMock(return_value=ToolResult("read", "hello"))

        loop = AgentLoop(provider=mock_provider, tools=[mock_read])
        messages = [Message(role="user", content="Read a file")]

        result, tool_calls, count = await loop.run_turn(messages, "gpt-4")

        assert "hello" in result
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "read"

    @pytest.mark.asyncio
    async def test_run_turn_max_tool_calls(self):
        """Test max_tool_calls limit per turn."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(
                content="",
                model="gpt-4",
                raw={
                    "tool_calls": [
                        {"id": f"call_{i}", "function": {"name": "tool", "arguments": json.dumps({"n": i})}}
                        for i in range(25)
                    ]
                },
            ),
            LLMResponse(content="Done", model="gpt-4"),
        ])

        mock_tool = MagicMock()
        mock_tool._tool_name = "tool"
        mock_tool.execute = MagicMock(return_value=ToolResult("tool", "ok"))

        config = AgentLoopConfig(max_tool_calls=10)
        loop = AgentLoop(provider=mock_provider, tools=[mock_tool], config=config)
        messages = [Message(role="user", content="Call many tools")]

        result, tool_calls, count = await loop.run_turn(messages, "gpt-4")

        # Should be capped at max_tool_calls
        assert count == 10
        assert len(tool_calls) == 10


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call_to_dict(self):
        """Test ToolCall serialization."""
        tc = ToolCall(name="read", arguments={"path": "a.txt"})
        result = tc.to_dict()

        assert result == {
            "name": "read",
            "arguments": {"path": "a.txt"},
        }


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_tool_result_with_error(self):
        """Test ToolResult with error."""
        result = ToolResult(
            name="read",
            content="",
            error="File not found",
        )
        assert result.error == "File not found"
        assert result.content == ""


class TestCreateAgentLoop:
    """Tests for create_agent_loop factory."""

    def test_create_with_provider(self):
        """Test create_agent_loop with explicit provider."""
        mock_provider = MagicMock()
        loop = create_agent_loop(model="gpt-4", provider=mock_provider)

        assert loop.provider is mock_provider

    def test_create_without_provider(self):
        """Test create_agent_loop auto-creates provider."""
        loop = create_agent_loop(model="gpt-4")
        assert loop.provider is not None