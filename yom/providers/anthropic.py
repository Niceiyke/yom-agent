"""Anthropic-compatible provider for yom.

Works with Anthropic's Claude models via the Anthropic API.

Usage:
    provider = AnthropicCompatibleProvider(api_key="sk-ant-...")
    
    # Or via factory
    provider = create_provider(
        provider="anthropic",
        model="claude-3-5-sonnet-latest",
        api_key="sk-ant-...",
    )
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator

from yom.providers.base import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    Usage,
)


class AnthropicCompatibleProvider(BaseProvider):
    """Anthropic-compatible provider using the official Anthropic SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ):
        """
        Initialize Anthropic-compatible provider.
        
        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            base_url: Custom API URL if needed.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._base_url = base_url or "https://api.anthropic.com"
        self._timeout = timeout
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "anthropic-compatible"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            
            # Set base_url via env var (required for MiniMax)
            if self._base_url:
                os.environ["ANTHROPIC_BASE_URL"] = self._base_url
            
            self._client = AsyncAnthropic(
                api_key=self._get_api_key(),
                timeout=self._timeout or 120.0,
            )
        return self._client

    def _get_api_key(self) -> str:
        """Get API key from config or environment."""
        if self._api_key:
            return self._api_key
        for var in ["ANTHROPIC_API_KEY", "MINIMAX_API_KEY", "API_KEY"]:
            key = os.environ.get(var)
            if key:
                return key
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    async def _retry_request(self, request_fn, config: CompletionConfig) -> Any:
        """Execute request with retry logic."""
        last_error: Exception | None = None
        for attempt in range(config.max_retries + 1):
            try:
                return await request_fn()
            except Exception as exc:
                last_error = exc
                if attempt < config.max_retries:
                    error_str = str(exc).lower()
                    if "rate_limit" in error_str or "429" in str(exc):
                        await asyncio.sleep((2 ** attempt) * 1.0)
                        continue
                    if "500" in str(exc):
                        await asyncio.sleep((2 ** attempt) * 0.5)
                        continue
                break
        raise last_error if last_error else RuntimeError("Request failed")

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send completion request to Anthropic."""
        config = config or CompletionConfig()

        # Convert messages to Anthropic format
        anthropic_messages = []
        system = ""
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            elif msg.role == "tool":
                tool_id = getattr(msg, "tool_call_id", None) or f"call_{id(msg)}"
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": msg.content,
                    }]
                })
            elif msg.role == "assistant" and getattr(msg, "_tool_calls", None):
                content = []
                for tc in msg._tool_calls:
                    tc_id = tc.get("id", f"call_{id(tc)}")
                    func = tc.get("function", {})
                    content.append({
                        "type": "tool_use",
                        "id": tc_id,
                        "name": func.get("name", ""),
                        "input": func.get("arguments", {}),
                    })
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        async def make_request():
            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": config.max_tokens,
            }
            if system:
                request_kwargs["system"] = system
            if config.temperature:
                request_kwargs["temperature"] = config.temperature
            if config.top_p is not None:
                request_kwargs["top_p"] = config.top_p
            if config.stop_sequences:
                request_kwargs["stop_sequences"] = config.stop_sequences
            if tools:
                # Convert tools to Anthropic format
                request_kwargs["tools"] = self._convert_tools(tools)

            return await self.client.messages.create(**request_kwargs)

        try:
            response = await self._retry_request(make_request, config)
        except Exception as exc:
            raise RuntimeError(f"Anthropic request failed: {exc}") from exc

        # Extract text content from all text blocks (skip thinking blocks)
        text = ""
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text += block.text
            elif hasattr(block, "type") and block.type == "thinking":
                # Thinking blocks are intentionally ignored in user-visible content.
                continue

        result = LLMResponse(
            content=text,
            model=response.model,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            stop_reason=response.stop_reason,
            raw={
                "content": response.content,
                "model": response.model,
                "stop_reason": response.stop_reason,
            },
        )
        
        # Validate (disabled by default, enable with YOM_VALIDATE=1)
        from yom.providers.validation import validate_anthropic_response, validate_message_format
        validate_message_format("anthropic", anthropic_messages)
        validate_anthropic_response(result)
        
        return result

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from Anthropic."""
        config = config or CompletionConfig()

        anthropic_messages = []
        system = ""
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": config.max_tokens,
        }
        if system:
            request_kwargs["system"] = system
        if config.temperature:
            request_kwargs["temperature"] = config.temperature
        if tools:
            request_kwargs["tools"] = self._convert_tools(tools)

        async with self.client.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield StreamChunk(
                            content=event.delta.text,
                            is_final=False,
                        )
                elif event.type == "message_delta":
                    if event.delta.stop_reason:
                        yield StreamChunk(
                            content="",
                            is_final=True,
                            stop_reason=event.delta.stop_reason,
                        )

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            })
        return anthropic_tools

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to Anthropic format."""
        result = []
        for msg in messages:
            if msg.role == "system":
                continue  # Handled separately in complete()
            elif msg.role == "tool":
                tool_id = getattr(msg, "tool_call_id", None) or f"call_{id(msg)}"
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": msg.content,
                    }]
                })
            elif msg.role == "assistant":
                # Check for tool_use blocks in metadata (MiniMax style)
                tool_calls = getattr(msg, "_tool_calls", None) or msg.metadata.get("_tool_calls")
                raw_content = msg.metadata.get("_raw_content")
                
                if tool_calls or raw_content:
                    # Build content blocks
                    content = []
                    
                    # Add any raw content blocks (for MiniMax tool_use)
                    if raw_content:
                        if isinstance(raw_content, list):
                            for block in raw_content:
                                if hasattr(block, 'type') and block.type == 'tool_use':
                                    # Convert ToolUseBlock to dict
                                    content.append({
                                        'type': 'tool_use',
                                        'id': getattr(block, 'id', None),
                                        'name': getattr(block, 'name', None),
                                        'input': getattr(block, 'input', {}),
                                    })
                        else:
                            content.append(raw_content)
                    
                    # Add tool_use blocks from _tool_calls
                    if tool_calls:
                        for tc in tool_calls:
                            tc_id = tc.get("id", f"call_{id(tc)}")
                            func = tc.get("function", {})
                            content.append({
                                "type": "tool_use",
                                "id": tc_id,
                                "name": func.get("name", ""),
                                "input": func.get("arguments", {}),
                            })
                    
                    result.append({"role": "assistant", "content": content})
                else:
                    result.append({"role": msg.role, "content": msg.content})
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

# Alias for backwards compatibility
AnthropicProvider = AnthropicCompatibleProvider


__all__ = ["AnthropicCompatibleProvider", "AnthropicProvider"]
