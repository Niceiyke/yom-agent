"""OpenAI-compatible provider implementation."""

from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from yom.providers.base import BaseProvider, CompletionConfig, LLMResponse, Message, StreamChunk, Usage


class OpenAIProvider(BaseProvider):
    """OpenAI-compatible provider using the official OpenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url or "https://api.openai.com/v1"
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._get_api_key(),
                base_url=self._base_url,
                timeout=120.0,
            )
        return self._client

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
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
                # Check both attribute and metadata for tool_calls
                tool_calls = getattr(msg, "_tool_calls", None) or msg.metadata.get("_tool_calls")
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
            result.append(msg_dict)
        return result

    def _get_api_key(self) -> str:
        api_key = self._api_key
        if not api_key:
            for env_var in ["OPENAI_API_KEY", "MINIMAX_API_KEY"]:
                api_key = os.environ.get(env_var)
                if api_key:
                    break
            if not api_key:
                raise ValueError("OPENAI_API_KEY or MINIMAX_API_KEY environment variable is required")
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
                    if "rate_limit" in str(exc).lower() or getattr(exc, "status_code", 0) == 429:
                        wait_time = (2 ** attempt) * 1.0
                        time.sleep(wait_time)
                        continue
                    if getattr(exc, "status_code", 0) >= 500:
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
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send completion request to OpenAI-compatible endpoint."""
        try:
            from openai import AsyncOpenAI, RateLimitError, APITimeoutError
        except ImportError as exc:
            raise ImportError(
                "OpenAI support requires installing 'openai' package: pip install openai"
            ) from exc

        config = config or CompletionConfig()
        
        # Validate and ensure unique tool call IDs
        messages = self.validate_tool_call_ids(messages)

        async def make_request():
            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": self.convert_messages(messages),
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
        except (RateLimitError, APITimeoutError) as exc:
            raise RuntimeError(f"OpenAI request failed after {config.max_retries} retries: {exc}") from exc

        if not response.choices:
            raise RuntimeError("OpenAI returned empty response")

        choice = response.choices[0]
        text = choice.message.content or ""
        finish_reason = choice.finish_reason or "error"

        tool_calls = []
        raw_response = {}
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                func = tc.function
                tool_calls.append({
                    "id": getattr(tc, "id", None),
                    "name": func.name,
                    "arguments": func.arguments,
                })
            raw_response["tool_calls"] = tool_calls

        usage = None
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        raw_data = response.model_dump() if hasattr(response, "model_dump") else {}
        if tool_calls:
            raw_data["tool_calls"] = tool_calls

        return LLMResponse(
            content=text,
            model=response.model,
            usage=usage,
            stop_reason=finish_reason,
            raw=raw_data,
        )

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from OpenAI-compatible endpoint."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAI support requires installing 'openai' package: pip install openai"
            ) from exc

        config = config or CompletionConfig()

        client = self.client

        openai_messages = [
            {"role": "system", "content": msg.content} if msg.role == "system"
            else {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": openai_messages,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if config.temperature:
            request_kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            request_kwargs["top_p"] = config.top_p
        if tools:
            request_kwargs["tools"] = tools

        stream = await client.chat.completions.create(**request_kwargs)

        has_content = False
        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                content = choice.delta.content or ""
                raw_data = {}
                
                if content:
                    has_content = True
                
                if choice.delta.tool_calls:
                    has_content = True
                    raw_data = {"tool_calls": [
                        {"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in choice.delta.tool_calls
                    ]}
                
                if content or raw_data:
                    yield StreamChunk(
                        content=content,
                        is_final=False,
                        raw=raw_data if raw_data else {},
                    )
                
                if choice.finish_reason:
                    yield StreamChunk(
                        content="",
                        is_final=True,
                        stop_reason=choice.finish_reason,
                    )
                    return

        if not has_content:
            yield StreamChunk(content="", is_final=True)
