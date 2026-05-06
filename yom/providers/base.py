"""Unified types for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
import time
import uuid


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
    """Unified message format for all providers."""
    role: str
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _tool_calls: list[dict[str, Any]] | None = None
    
    def __post_init__(self):
        # Auto-generate unique ID for tool calls if needed
        if self.role == "tool" and self.tool_call_id is None:
            self.tool_call_id = f"call_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to provider-specific dict format."""
        result = {"role": self.role, "content": self.content}
        
        if self.role == "tool":
            if self.tool_call_id:
                result["tool_call_id"] = self.tool_call_id
            if self.name:
                result["name"] = self.name
        elif self.role == "assistant" and self._tool_calls:
            result["tool_calls"] = self._tool_calls
            
        return result
    
    def to_openai_dict(self) -> dict[str, Any]:
        """Convert to OpenAI format."""
        result = {"role": self.role, "content": self.content}
        
        if self.role == "tool":
            result["tool_call_id"] = self.tool_call_id or f"call_{uuid.uuid4().hex[:8]}"
            result["name"] = self.name
        elif self.role == "assistant" and self._tool_calls:
            result["tool_calls"] = self._tool_calls
            
        return result
    
    def to_anthropic_dict(self) -> dict[str, Any]:
        """Convert to Anthropic format."""
        if self.role == "system":
            return {"role": "system", "content": self.content}
        
        if self.role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": self.tool_call_id or f"call_{uuid.uuid4().hex[:8]}",
                        "content": self.content,
                    }
                ]
            }
        
        if self.role == "assistant" and self._tool_calls:
            content = []
            for tc in self._tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "name": tc.get("function", {}).get("name", ""),
                    "input": tc.get("function", {}).get("arguments", {}),
                })
            return {"role": "assistant", "content": content}
        
        return {"role": self.role, "content": self.content}
    
    def to_google_dict(self) -> dict[str, Any]:
        """Convert to Google format."""
        if self.role == "system":
            return {"role": "system", "parts": [{"text": self.content}]}
        
        if self.role == "tool":
            return {
                "role": "model",
                "parts": [{
                    "functionResponse": {
                        "name": self.name or "unknown",
                        "response": {"content": self.content}
                    }
                }]
            }
        
        if self.role == "assistant" and self._tool_calls:
            parts = []
            for tc in self._tool_calls:
                parts.append({
                    "functionCall": {
                        "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "name": tc.get("function", {}).get("name", ""),
                        "args": tc.get("function", {}).get("arguments", {}),
                    }
                })
            return {"role": "model", "parts": parts}
        
        return {"role": "user" if self.role == "user" else "model", "parts": [{"text": self.content}]}


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    # Provider capabilities
    SUPPORTS_TOOLS: bool = True
    SUPPORTS_STREAMING: bool = True
    SUPPORTS_SYSTEM_MESSAGE: bool = True
    
    # API endpoint info
    base_url: str | None = None
    api_key: str | None = None
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai')."""
        ...
    
    @property
    def supports_tools(self) -> bool:
        """Check if provider supports tool calling."""
        return self.SUPPORTS_TOOLS
    
    @property
    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        return self.SUPPORTS_STREAMING
    
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
    
    def convert_tool_result(self, result: dict[str, Any], tool_call_id: str, name: str) -> dict[str, Any]:
        """Convert a tool result to provider-specific format.
        
        Args:
            result: Tool execution result dict with 'content' and optional 'error'
            tool_call_id: ID of the tool call
            name: Name of the tool
            
        Returns:
            Tool result dict in provider format
        """
        # Default: OpenAI format
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result.get("content", ""),
        }
    
    def validate_tool_call_ids(self, messages: list[Message]) -> list[Message]:
        """Ensure all tool call IDs are unique and valid.
        
        Some providers (like MiniMax) require unique IDs across the entire conversation.
        This method ensures no duplicate IDs exist.
        """
        seen_ids: set[str] = set()
        
        for msg in messages:
            if msg.role == "assistant" and msg._tool_calls:
                for tc in msg._tool_calls:
                    tc_id = tc.get("id")
                    if tc_id in seen_ids:
                        # Generate new unique ID
                        tc["id"] = f"call_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
                    seen_ids.add(tc["id"])
            
            if msg.role == "tool":
                if msg.tool_call_id in seen_ids:
                    msg.tool_call_id = f"call_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
                seen_ids.add(msg.tool_call_id)
        
        return messages