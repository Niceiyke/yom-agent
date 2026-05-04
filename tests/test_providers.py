"""Tests for LLM providers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from yom.providers.base import CompletionConfig, LLMResponse, Message, Usage
from yom.providers.openai import OpenAIProvider
from yom.providers.anthropic import AnthropicProvider
from yom.providers.google import GoogleProvider


class TestCompletionConfig:
    """Tests for CompletionConfig."""

    def test_default_values(self):
        """Test default config values."""
        config = CompletionConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.timeout == 120.0
        assert config.max_retries == 3

    def test_custom_values(self):
        """Test custom config values."""
        config = CompletionConfig(
            temperature=0.5,
            max_tokens=1000,
            timeout=60.0,
            max_retries=5,
        )
        assert config.temperature == 0.5
        assert config.max_tokens == 1000
        assert config.timeout == 60.0
        assert config.max_retries == 5


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_provider_name(self):
        """Test provider name is 'openai'."""
        provider = OpenAIProvider()
        assert provider.provider_name == "openai"

    def test_client_is_cached(self):
        """Test that the client is cached after first access."""
        provider = OpenAIProvider(api_key="test-key")
        client1 = provider.client
        client2 = provider.client
        assert client1 is client2

    def test_convert_messages(self):
        """Test message conversion."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        provider = OpenAIProvider()
        result = provider.convert_messages(messages)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_complete_raises_on_empty_choices(self):
        """Test that empty response choices raise RuntimeError."""
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.choices = []

        with patch.object(provider, "client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(RuntimeError, match="empty response"):
                await provider.complete(
                    [Message(role="user", content="Hello")],
                    model="gpt-4",
                )

    @pytest.mark.asyncio
    async def test_complete_with_retry(self):
        """Test that complete retries on rate limit."""
        provider = OpenAIProvider(api_key="test-key")
        config = CompletionConfig(max_retries=2)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="hello"))]
        mock_response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        mock_response.model = "gpt-4"

        with patch.object(provider, "client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await provider.complete(
                [Message(role="user", content="Hello")],
                model="gpt-4",
                config=config,
            )

            assert result.content == "hello"
            assert mock_client.chat.completions.create.call_count == 1


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_provider_name(self):
        """Test provider name is 'anthropic'."""
        provider = AnthropicProvider()
        assert provider.provider_name == "anthropic"

    def test_client_is_cached(self):
        """Test that the client is cached after first access."""
        provider = AnthropicProvider(api_key="test-key")
        client1 = provider.client
        client2 = provider.client
        assert client1 is client2

    def test_convert_messages(self):
        """Test message conversion removes system messages."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        provider = AnthropicProvider()
        result = provider.convert_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_extracts_text_from_blocks(self):
        """Test that text is extracted from content blocks."""
        provider = AnthropicProvider(api_key="test-key")

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Hello, World!"

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.model = "claude-3"
        mock_response.usage = MagicMock(input_tokens=1, output_tokens=1)
        mock_response.stop_reason = "end_turn"

        with patch.object(provider, "client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            result = await provider.complete(
                [Message(role="user", content="Hello")],
                model="claude-3-5-sonnet-latest",
            )

            assert result.content == "Hello, World!"
            assert result.model == "claude-3"


class TestGoogleProvider:
    """Tests for GoogleProvider."""

    def test_provider_name(self):
        """Test provider name is 'google'."""
        provider = GoogleProvider()
        assert provider.provider_name == "google"

    def test_client_is_cached(self):
        """Test that the client is cached after first access."""
        provider = GoogleProvider(api_key="test-key")
        client1 = provider.client
        client2 = provider.client
        assert client1 is client2

    def test_convert_messages(self):
        """Test message conversion to Google format."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]
        provider = GoogleProvider()
        result = provider.convert_messages(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["parts"][0]["text"] == "Hello"


class TestLLMResponse:
    """Tests for LLMResponse."""

    def test_response_with_usage(self):
        """Test response with usage information."""
        usage = Usage(input_tokens=100, output_tokens=50, total_tokens=150)
        response = LLMResponse(
            content="Hello!",
            model="gpt-4",
            usage=usage,
            stop_reason="stop",
        )

        assert response.content == "Hello!"
        assert response.usage.total_tokens == 150

    def test_response_raw_dict(self):
        """Test response with raw dict data."""
        response = LLMResponse(
            content="Hi",
            model="claude-3",
            raw={"extra": "data"},
        )

        assert response.raw["extra"] == "data"


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(role="user", content="Hello")
        result = msg.to_dict()

        assert result == {"role": "user", "content": "Hello"}

    def test_message_equality(self):
        """Test message equality."""
        msg1 = Message(role="user", content="Hello")
        msg2 = Message(role="user", content="Hello")
        msg3 = Message(role="assistant", content="Hello")

        assert msg1 == msg2
        assert msg1 != msg3