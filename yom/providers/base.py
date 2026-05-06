"""Unified types for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class Usage:
    """Token usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Provider-agnostic response from LLM."""
    content: str
    model: str
    usage: Usage | None = None
    stop_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletionConfig:
    """Configuration for completion requests."""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float | None = None
    stop_sequences: list[str] = field(default_factory=list)
    timeout: float = 120.0
    max_retries: int = 3


@dataclass
class StreamChunk:
    """A chunk of a streaming response."""
    content: str = ""
    is_final: bool = False
    stop_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Unified message format."""
    role: str
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {"role": self.role, "content": self.content}
        if self.role == "tool":
            if self.tool_call_id:
                result["tool_call_id"] = self.tool_call_id
            if self.name:
                result["name"] = self.name
        return result


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai')."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a completion request."""
        ...

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion response."""
        # Default implementation - use complete and yield chunks
        full_response = await self.complete(messages, model, config, tools)
        if full_response.content:
            yield StreamChunk(
                content=full_response.content,
                is_final=True,
                stop_reason=full_response.stop_reason,
                raw={},
            )

    @abstractmethod
    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to provider-specific format."""
        ...
