"""Tests for context management."""

from __future__ import annotations

import pytest

from yom.context import (
    ApproximateTokenCounter,
    ContextConfig,
    ContextManager,
    ContextStats,
    TruncationStrategy,
    create_token_counter,
    estimate_tokens,
)


class TestApproximateTokenCounter:
    """Tests for ApproximateTokenCounter."""

    def test_count_basic(self):
        """Test basic token counting."""
        counter = ApproximateTokenCounter()
        result = counter.count("hello world")
        assert result >= 1

    def test_count_empty(self):
        """Test empty string."""
        counter = ApproximateTokenCounter()
        assert counter.count("") == 1

    def test_count_long_text(self):
        """Test longer text."""
        counter = ApproximateTokenCounter()
        text = " ".join(["hello"] * 100)
        result = counter.count(text)
        assert result > 100


class TestCreateTokenCounter:
    """Tests for create_token_counter factory."""

    def test_create_approximate(self):
        """Test creating approximate counter."""
        counter = create_token_counter("approximate")
        assert isinstance(counter, ApproximateTokenCounter)

    def test_create_auto(self):
        """Test auto creation returns a valid counter."""
        counter = create_token_counter("auto")
        assert counter is not None


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_estimate_character(self):
        """Test character-based estimation."""
        result = estimate_tokens("hello world", method="character")
        assert result >= 1

    def test_estimate_words(self):
        """Test word-based estimation."""
        result = estimate_tokens("hello world", method="words")
        assert result >= 1

    def test_estimate_auto(self):
        """Test auto estimation."""
        result = estimate_tokens("hello world", method="auto")
        assert result >= 1


class TestContextConfig:
    """Tests for ContextConfig."""

    def test_default_values(self):
        """Test default configuration."""
        config = ContextConfig()
        assert config.max_tokens == 128000
        assert config.tokenizer_backend == "auto"
        assert config.strategy == TruncationStrategy.TRUNCATE
        assert config.preserve_system_prompt is True
        assert config.preserve_last_n_messages == 0

    def test_custom_values(self):
        """Test custom configuration."""
        config = ContextConfig(
            max_tokens=50000,
            tokenizer_backend="approximate",
            strategy=TruncationStrategy.SUMMARIZE,
            preserve_last_n_messages=2,
        )
        assert config.max_tokens == 50000
        assert config.strategy == TruncationStrategy.SUMMARIZE
        assert config.preserve_last_n_messages == 2


class TestContextManager:
    """Tests for ContextManager."""

    @pytest.fixture
    def manager(self):
        """Create a context manager with approximate counter."""
        config = ContextConfig(
            max_tokens=1000,
            tokenizer_backend="approximate",
        )
        return ContextManager(config)

    def test_count_tokens(self, manager):
        """Test token counting."""
        result = manager.count_tokens("hello world")
        assert result >= 2

    def test_count_message_tokens(self, manager):
        """Test message token counting."""
        msg = {"role": "user", "content": "hello"}
        tokens = manager.count_message_tokens(msg)
        assert tokens >= 2

    def test_count_messages_tokens(self, manager):
        """Test multiple message token counting."""
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        total = manager.count_messages_tokens(messages)
        assert total >= 4

    def test_truncate_empty_messages(self, manager):
        """Test truncating empty message list."""
        result = manager.truncate_messages([])
        assert result == []

    def test_truncate_messages_under_limit(self, manager):
        """Test no truncation when under limit."""
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        result = manager.truncate_messages(messages)
        assert len(result) == 2

    def test_truncate_messages_over_limit(self, manager):
        """Test truncation when over limit."""
        messages = [
            {"role": "user", "content": "This is a long message " * 100},
            {"role": "assistant", "content": "This is also a long response " * 100},
            {"role": "user", "content": "Another message"},
        ]
        result = manager.truncate_messages(messages)
        assert manager.count_messages_tokens(result) <= manager.max_tokens

    def test_truncate_preserves_tail(self):
        """Test truncation with preserve_tail."""
        config = ContextConfig(
            max_tokens=100,
            tokenizer_backend="approximate",
            preserve_last_n_messages=1,
        )
        manager = ContextManager(config)

        messages = [
            {"role": "user", "content": "Early message " * 50},
            {"role": "assistant", "content": "Middle message " * 50},
            {"role": "user", "content": "tail"},
        ]
        result = manager.truncate_messages(messages)
        assert result[-1]["content"] == "tail"

    def test_get_stats(self, manager):
        """Test getting context statistics."""
        messages = [
            {"role": "user", "content": "hello"},
        ]
        stats = manager.get_stats(messages)
        assert isinstance(stats, ContextStats)
        assert stats.total_tokens > 0
        assert stats.message_count == 1
        assert stats.max_tokens == 1000


class TestTruncationStrategy:
    """Tests for TruncationStrategy enum."""

    def test_values(self):
        """Test enum values."""
        assert TruncationStrategy.TRUNCATE == "truncate"
        assert TruncationStrategy.SUMMARIZE == "summarize"
        assert TruncationStrategy.TRUNCATE_AND_SUMMARIZE == "truncate_and_summarize"