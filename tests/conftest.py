"""Pytest configuration and fixtures."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from yom import AgentState, Message
from yom.providers import CompletionConfig, LLMResponse, Usage


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_state() -> AgentState:
    """Create a sample agent state."""
    state = AgentState.create(
        runtime_id="test-runtime",
        session_id="test-session",
        max_turns=10,
    )
    state.add_user_message("Hello")
    state.add_assistant_message("Hi there!")
    return state


@pytest.fixture
def sample_messages() -> list[Message]:
    """Create sample messages."""
    return [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ]


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.provider_name = "mock"

    async def mock_complete(messages, model, config=None):
        return LLMResponse(
            content="Mock response",
            model=model,
            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30),
            stop_reason="stop",
        )

    provider.complete = AsyncMock(side_effect=mock_complete)
    provider.stream = AsyncMock()
    provider.convert_messages = MagicMock(return_value=[])
    return provider


@pytest.fixture
def mock_config() -> CompletionConfig:
    """Create a sample completion config."""
    return CompletionConfig(
        temperature=0.7,
        max_tokens=100,
        timeout=30.0,
        max_retries=3,
    )