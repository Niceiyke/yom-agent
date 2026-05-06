"""Anthropic provider implementation."""

from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from yom.providers.base import BaseProvider, CompletionConfig, LLMResponse, Message, StreamChunk, Usage


class AnthropicProvider(BaseProvider):
    """Anthropic provider using the official Anthropic SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url or "https://api.anthropic.com"
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(
                api_key=self._get_api_key(),
                base_url=self._base_url,
            )
        return self._client

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to Anthropic format."""
        result = []
        for msg in messages:
            if msg.role == "system":
                continue  # System messages handled separately
            result.append({
                "role": msg.role,
                "content": msg.content,
            })
        return result

    def _get_api_key(self) -> str:
        api_key = self._api_key
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                api_key = os.environ.get("MINIMAX_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY or MINIMAX_API_KEY environment variable is required"
                )
        return api_key

    async def _retry_request(self, request_fn, config: CompletionConfig) -> Any:
        """Execute request with retry logic for transient failures."""
        last_error: Exception | None = None
        for attempt in range(config.max_retries + 1):
            try:
                return await request_fn()
            except Exception as exc:
                last_error = exc
                if attempt < config.max_retries:
                    error_str = str(exc).lower()
                    if "rate_limit" in error_str or "429" in error_str:
                        wait_time = (2 ** attempt) * 1.0
                        time.sleep(wait_time)
                        continue
                    if "500" in error_str or "502" in error_str or "503" in error_str:
                        wait_time = (2 ** attempt) * 0.5
                        time.sleep(wait_time)
                        continue
                break
        raise last_error if last_error else RuntimeError("Request failed")

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,  # type: ignore[override]
    ) -> LLMResponse:
        """Send completion request to Anthropic."""
        try:
            from anthropic import AsyncAnthropic, RateLimitError
        except ImportError as exc:
            raise ImportError(
                "Anthropic support requires installing 'anthropic' package: pip install anthropic"
            ) from exc

        config = config or CompletionConfig()

        system = ""
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        async def make_request():
            request_kwargs = {
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
            return await self.client.messages.create(**request_kwargs)

        try:
            response = await self._retry_request(make_request, config)
        except (RateLimitError, Exception) as exc:
            raise RuntimeError(f"Anthropic request failed after {config.max_retries} retries: {exc}") from exc

        text = ""
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text += block.text

        return LLMResponse(
            content=text,
            model=response.model,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            stop_reason=response.stop_reason,
            raw={"content": response.content, "model": response.model, "stop_reason": response.stop_reason},
        )

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,  # type: ignore[override]
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from Anthropic."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ImportError(
                "Anthropic support requires installing 'anthropic' package: pip install anthropic"
            ) from exc

        config = config or CompletionConfig()

        client = self.client  # Use cached client

        system = ""
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})


        request_kwargs = {
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

        text_content = ""

        async with client.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        text_content += event.delta.text
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

        final = await stream.get_final_message()
        yield StreamChunk(
            content="",
            is_final=True,
            stop_reason=final.stop_reason,
        )
