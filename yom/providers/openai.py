"""OpenAI-compatible provider for yom.

Works with ANY API that follows the OpenAI chat completions format:
- OpenAI (api.openai.com)
- Azure OpenAI (use azure=True)
- Ollama (localhost:11434/v1)
- LM Studio (localhost:1234/v1)
- Groq (api.groq.com)
- Fireworks (api.fireworks.ai)
- Together AI (api.together.xyz)
- vLLM, SGLang, and any other OpenAI-compatible server

Usage:
    # Direct
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",  # Ollama
        api_key="ollama",  # or None for Ollama
    )

    # Via factory
    provider = create_provider(
        base_url="http://localhost:11434/v1",
        model="llama3",
    )
"""

from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from yom.providers.base import BaseProvider, CompletionConfig, LLMResponse, Message, StreamChunk, Usage


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible provider using the official OpenAI SDK.

    Works with any server that implements the OpenAI chat completions API format.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        """
        Initialize OpenAI-compatible provider.

        Args:
            base_url: API base URL. Defaults to OpenAI (https://api.openai.com/v1)
            api_key: API key. Defaults to OPENAI_API_KEY env var.
                     Many servers (Ollama, LM Studio) don't need one.
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url or "https://api.openai.com/v1"
        self._api_key = api_key
        self._timeout = timeout
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "openai-compatible"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._get_api_key(),
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def _get_api_key(self) -> str:
        """Get API key from config or environment."""
        if self._api_key:
            return self._api_key
        # Check common env vars
        for var in ["OPENAI_API_KEY", "MINIMAX_API_KEY", "API_KEY"]:
            key = os.environ.get(var)
            if key:
                return key
        # Many servers don't require an API key
        return "not-needed"

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
                    if "rate_limit" in error_str or "429" in str(getattr(exc, "status_code", "")):
                        time.sleep((2 ** attempt) * 1.0)
                        continue
                    if "500" in str(getattr(exc, "status_code", "")):
                        time.sleep((2 ** attempt) * 0.5)
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
        """Send completion request to OpenAI-compatible endpoint."""
        config = config or CompletionConfig()

        async def make_request():
            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": self._convert_messages(messages),
                "max_tokens": config.max_tokens,
            }
            if config.temperature:
                request_kwargs["temperature"] = config.temperature
            if config.top_p is not None:
                request_kwargs["top_p"] = config.top_p
            if config.stop_sequences:
                request_kwargs["stop"] = config.stop_sequences
            if tools:
                request_kwargs["tools"] = tools

            return await self.client.chat.completions.create(**request_kwargs)

        try:
            response = await self._retry_request(make_request, config)
        except Exception as exc:
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc

        if not response.choices:
            raise RuntimeError("OpenAI returned empty response")

        choice = response.choices[0]
        text = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"

        # Extract tool calls if present
        tool_calls = []
        raw_data = {}
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                func = tc.function
                tool_calls.append({
                    "id": getattr(tc, "id", None),
                    "name": func.name,
                    "arguments": func.arguments,
                })
            raw_data["tool_calls"] = tool_calls

        # Usage
        usage = None
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        raw_data.update(response.model_dump() if hasattr(response, "model_dump") else {})
        
        result = LLMResponse(
            content=text,
            model=response.model,
            usage=usage,
            stop_reason=finish_reason,
            raw=raw_data,
        )
        
        # Validate (disabled by default, enable with YOM_VALIDATE=1)
        from yom.providers.validation import validate_openai_response, validate_message_format
        validate_message_format("openai", self._convert_messages(messages))
        validate_openai_response(result)
        
        return result

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from OpenAI-compatible endpoint."""
        config = config or CompletionConfig()

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if config.temperature:
            request_kwargs["temperature"] = config.temperature
        if tools:
            request_kwargs["tools"] = tools

        stream_response = await self.client.chat.completions.create(**request_kwargs)

        has_content = False
        async for chunk in stream_response:
            if chunk.choices:
                choice = chunk.choices[0]
                content = choice.delta.content or ""
                raw_data = {}

                if content:
                    has_content = True
                    yield StreamChunk(content=content, is_final=False)

                if choice.delta.tool_calls:
                    has_content = True
                    raw_data["tool_calls"] = [
                        {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in choice.delta.tool_calls
                    ]
                    yield StreamChunk(content="", is_final=False, raw=raw_data)

                if choice.finish_reason:
                    yield StreamChunk(content="", is_final=True, stop_reason=choice.finish_reason)
                    return

        if not has_content:
            yield StreamChunk(content="", is_final=True)

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to OpenAI format."""
        result = []
        for msg in messages:
            msg_dict: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.role == "tool":
                msg_dict["tool_call_id"] = getattr(msg, "tool_call_id", None)
                msg_dict["name"] = getattr(msg, "name", None)
            elif msg.role == "assistant":
                tool_calls = getattr(msg, "_tool_calls", None) or msg.metadata.get("_tool_calls")
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
            result.append(msg_dict)
        return result

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to OpenAI format."""
        return self._convert_messages(messages)


# Alias for backwards compatibility
OpenAIProvider = OpenAICompatibleProvider


__all__ = ["OpenAICompatibleProvider", "OpenAIProvider"]
