"""Token counting utilities for context management."""

from __future__ import annotations

import importlib.util
from typing import Protocol


class TokenCounter(Protocol):
    """Protocol for token counting implementations."""

    def count(self, text: str) -> int:
        """Count tokens in text."""
        ...


class TiktokenCounter:
    """Token counter using tiktoken library."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        try:
            import tiktoken
            self._encoding: tiktoken.Encoding | None = tiktoken.get_encoding(encoding_name)
        except ImportError:
            self._encoding = None
            self._encoding_name = encoding_name

    def count(self, text: str) -> int:
        """Count tokens using tiktoken."""
        if self._encoding is None:
            return self._approx_count(text)
        try:
            return len(self._encoding.encode(text))
        except Exception:
            return self._approx_count(text)

    def _approx_count(self, text: str) -> int:
        """Fallback approximate token count."""
        return len(text) // 4


class ApproximateTokenCounter:
    """Simple approximate token counter based on character count."""

    CHARS_PER_TOKEN = 4

    def count(self, text: str) -> int:
        """Approximate tokens as characters / CHARS_PER_TOKEN."""
        return max(1, len(text) // self.CHARS_PER_TOKEN)


class HuggingFaceTokenizerCounter:
    """Token counter using HuggingFace transformers."""

    def __init__(self, model_name: str = "gpt2"):
        try:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        except ImportError:
            self._tokenizer = None

    def count(self, text: str) -> int:
        """Count tokens using HuggingFace tokenizer."""
        if self._tokenizer is None:
            return ApproximateTokenCounter().count(text)
        try:
            return len(self._tokenizer.encode(text))
        except Exception:
            return ApproximateTokenCounter().count(text)


def create_token_counter(
    backend: str = "auto",
    model: str | None = None,
) -> TokenCounter:
    """Create a token counter with the specified backend.

    Args:
        backend: "tiktoken", "huggingface", "approximate", or "auto"
        model: Model name for HuggingFace backend

    Returns:
        TokenCounter instance
    """
    if backend == "tiktoken":
        return TiktokenCounter()
    elif backend == "huggingface":
        return HuggingFaceTokenizerCounter(model or "gpt2")
    elif backend == "approximate":
        return ApproximateTokenCounter()
    elif backend == "auto":
        if importlib.util.find_spec("tiktoken") is not None:
            return TiktokenCounter()
        if importlib.util.find_spec("transformers") is not None:
            return HuggingFaceTokenizerCounter()
        return ApproximateTokenCounter()
    else:
        return ApproximateTokenCounter()


def count_messages_tokens(messages: list[dict], token_counter: TokenCounter | None = None) -> int:
    """Count total tokens in a list of messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        token_counter: Token counter to use (creates default if None)

    Returns:
        Total token count
    """
    if token_counter is None:
        token_counter = create_token_counter()

    total = 0
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        total += token_counter.count(content)
        total += token_counter.count(f"{role}:")
    total += token_counter.count("<|endoftext|>")
    return total


def estimate_tokens(text: str, method: str = "auto") -> int:
    """Estimate token count for text.

    Args:
        text: Text to count
        method: "auto", "tiktoken", "character", or "words"

    Returns:
        Estimated token count
    """
    if method == "character":
        return max(1, len(text) // 4)
    elif method == "words":
        return len(text.split()) * 4 // 3
    elif method == "tiktoken":
        counter = create_token_counter("tiktoken")
        return counter.count(text)
    else:
        counter = create_token_counter("auto")
        return counter.count(text)