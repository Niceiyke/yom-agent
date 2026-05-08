"""Context management for handling context window limits."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from yom.models.messages import Message


logger = logging.getLogger(__name__)


class TruncationStrategy(str, Enum):
    """Strategy for handling context overflow."""

    TRUNCATE = "truncate"
    SUMMARIZE = "summarize"
    TRUNCATE_AND_SUMMARIZE = "truncate_and_summarize"


class ContextStats(BaseModel):
    """Statistics about context usage."""

    total_tokens: int
    max_tokens: int
    message_count: int
    utilization_pct: float


class ContextConfig(BaseModel):
    """Configuration for context management."""

    max_tokens: int = 128000
    tokenizer_backend: str = "auto"
    strategy: TruncationStrategy = TruncationStrategy.TRUNCATE
    preserve_system_prompt: bool = True
    preserve_last_n_messages: int = 0
    summarizer_fn: Callable[[list[dict]], str] | None = None

    model_config = {"arbitrary_types_allowed": True}


class ContextManager:
    """Manages context window by truncating or summarizing messages.

    Usage:
        config = ContextConfig(max_tokens=100000)
        manager = ContextManager(config)

        truncated = manager.truncate_messages(messages)
    """

    def __init__(
        self,
        config: ContextConfig | None = None,
        token_counter: "TokenCounter | None" = None,
    ):
        self.config = config or ContextConfig()
        from yom.context.tokenizer import TokenCounter, create_token_counter
        self._token_counter = token_counter or create_token_counter(
            self.config.tokenizer_backend
        )

    @property
    def max_tokens(self) -> int:
        """"Get max tokens limit."""
        return self.config.max_tokens

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return self._token_counter.count(text)

    def count_message_tokens(self, msg: dict) -> int:
        """Count tokens in a message dict."""
        role = msg.get("role", "")
        content = msg.get("content", "")
        overhead = self._token_counter.count(f"{role}: ")
        return self._token_counter.count(content) + overhead

    def count_messages_tokens(self, messages: list[dict]) -> int:
        """Count total tokens in messages."""
        return sum(self.count_message_tokens(msg) for msg in messages)

    def truncate_messages(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
    ) -> list[dict]:
        """Truncate messages to fit within token limit.

        Args:
            messages: List of message dicts
            max_tokens: Override max tokens (uses config default if None)

        Returns:
            Truncated message list
        """
        if not messages:
            return []

        max_tokens = max_tokens or self.config.max_tokens
        if self.config.preserve_last_n_messages > 0:
            return self._truncate_with_preserve_tail(messages, max_tokens)

        return self._truncate_from_front(messages, max_tokens)

    def _truncate_from_front(
        self,
        messages: list[dict],
        max_tokens: int,
    ) -> list[dict]:
        """Truncate from the front, keeping most recent messages."""
        result: list[dict] = []
        total_tokens = 0

        for msg in reversed(messages):
            msg_tokens = self.count_message_tokens(msg)
            if total_tokens + msg_tokens <= max_tokens:
                result.insert(0, msg)
                total_tokens += msg_tokens
            else:
                break

        if not result and messages:
            content = messages[-1].get("content", "")
            truncated_content = self._truncate_content(content, max_tokens)
            result = [{**messages[-1], "content": truncated_content}]

        logger.debug(
            f"Truncated {len(messages) - len(result)} messages, "
            f"{self.count_messages_tokens(result)} tokens"
        )
        return result

    def _truncate_with_preserve_tail(
        self,
        messages: list[dict],
        max_tokens: int,
    ) -> list[dict]:
        """Truncate but preserve last N messages."""
        preserve = self.config.preserve_last_n_messages
        tail = messages[-preserve:] if preserve > 0 else []
        head = messages[:-preserve] if preserve > 0 else messages[:-1]

        truncated_head = self._truncate_from_front(head, max_tokens - self.count_messages_tokens(tail))

        return truncated_head + tail

    def _truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncate single content string to fit tokens."""
        max_chars = max_tokens * 4
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "\n[truncated...]"

    def summarize_messages(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
    ) -> list[dict]:
        """Summarize older messages to make room.

        Uses the configured summarizer or creates a generic summary.

        Args:
            messages: List of message dicts
            max_tokens: Override max tokens

        Returns:
            Messages with older ones summarized
        """
        if not messages:
            return []

        max_tokens = max_tokens or self.config.max_tokens

        if self.count_messages_tokens(messages) <= max_tokens:
            return messages

        summarizer = self.config.summarizer_fn
        if summarizer:
            return self._summarize_with_fn(messages, max_tokens, summarizer)

        return self._generic_summarize(messages, max_tokens)

    def _summarize_with_fn(
        self,
        messages: list[dict],
        max_tokens: int,
        summarizer: Callable[[list[dict]], str],
    ) -> list[dict]:
        """Summarize using a custom function."""
        summary = summarizer(messages)
        summary_tokens = self.count_tokens(summary)
        available = max_tokens - summary_tokens - self.count_messages_tokens(messages[-2:])

        if available < 0:
            return [
                {"role": "system", "content": summary},
                messages[-2],
                messages[-1],
            ]

        truncated = self._truncate_from_front(messages[:-2], available)
        return truncated + [messages[-2], messages[-1], {"role": "system", "content": summary}]

    def _generic_summarize(
        self,
        messages: list[dict],
        max_tokens: int,
    ) -> list[dict]:
        """Create a generic summary of conversation."""
        total_count = len(messages)
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

        summary = (
            f"Conversation summary: {total_count} messages total. "
            f"{len(user_msgs)} from user, {len(assistant_msgs)} from assistant."
        )

        last_msgs = messages[-4:]
        result = [msg for msg in messages if msg not in last_msgs]

        summary_tokens = self.count_tokens(summary)
        last_tokens = self.count_messages_tokens(last_msgs)
        available = max_tokens - summary_tokens - last_tokens

        if available < 0:
            result = []
            last_msgs = self._truncate_from_front(last_msgs, max_tokens - summary_tokens)

        return [{"role": "system", "content": summary}] + last_msgs

    def get_stats(self, messages: list[dict]) -> ContextStats:
        """Get context usage statistics."""
        total = self.count_messages_tokens(messages)
        return ContextStats(
            total_tokens=total,
            max_tokens=self.config.max_tokens,
            message_count=len(messages),
            utilization_pct=(total / self.config.max_tokens * 100) if self.config.max_tokens > 0 else 0,
        )


_default_manager: ContextManager | None = None


def get_default_context_manager() -> ContextManager:
    """Get the default context manager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ContextManager()
    return _default_manager


def set_default_context_manager(manager: ContextManager) -> None:
    """Set the default context manager."""
    global _default_manager
    _default_manager = manager
