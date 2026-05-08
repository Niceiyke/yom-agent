"""OpenAI Chat Completions provider.

This provider intentionally targets the documented OpenAI Chat Completions API
surface implemented by OpenAI and many compatible servers. In most cases adding
another compatible provider only requires changing ``model`` and ``base_url``.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any, AsyncIterator

from yom.providers.base import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    Usage,
)


class OpenAICompatibleProvider(BaseProvider):
    """Provider for OpenAI-compatible Chat Completions APIs."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    ENV_API_KEYS = ("OPENAI_API_KEY", "MINIMAX_API_KEY", "API_KEY")

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        default_headers: dict[str, str] | None = None,
        default_query: dict[str, Any] | None = None,
    ) -> None:
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._default_headers = default_headers
        self._default_query = default_query
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def client(self) -> Any:
        """Return a cached official OpenAI async client."""
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._get_api_key(),
                base_url=self._base_url,
                timeout=self._timeout,
                default_headers=self._default_headers,
                default_query=self._default_query,
                max_retries=0,  # yom owns retry policy through CompletionConfig.
            )
        return self._client

    @client.setter
    def client(self, value: Any) -> None:
        # Kept for tests and advanced dependency injection.
        self._client = value

    @client.deleter
    def client(self) -> None:
        self._client = None

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        for env_var in self.ENV_API_KEYS:
            if key := os.environ.get(env_var):
                return key
        # OpenAI-compatible local servers commonly accept any non-empty key.
        return "not-needed"

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        code = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
        try:
            return int(code) if code is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        code = cls._status_code(exc)
        if code in {408, 409, 429} or (code is not None and code >= 500):
            return True
        text = str(exc).lower()
        return any(marker in text for marker in ("rate limit", "rate_limit", "timeout", "temporar"))

    async def _retry_request(self, request_fn: Callable[[], Awaitable[Any]], config: CompletionConfig) -> Any:
        last_error: Exception | None = None
        for attempt in range(config.max_retries + 1):
            try:
                return await request_fn()
            except Exception as exc:  # SDK-specific exceptions vary across compatible servers.
                last_error = exc
                if attempt >= config.max_retries or not self._is_retryable(exc):
                    break
                await asyncio.sleep(min(30.0, 0.5 * (2**attempt)))
        raise last_error if last_error else RuntimeError("OpenAI request failed")

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Create a non-streaming chat completion."""
        config = config or CompletionConfig()
        request_kwargs = self._build_request_kwargs(messages, model, config, tools, stream=False)

        try:
            response = await self._retry_request(
                lambda: self.client.chat.completions.create(**request_kwargs),
                config,
            )
        except Exception as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        choices = getattr(response, "choices", None) or []
        if not choices:
            raise RuntimeError("OpenAI returned empty response")

        choice = choices[0]
        message = choice.message
        tool_calls = self._extract_tool_calls(getattr(message, "tool_calls", None))
        raw = response.model_dump() if callable(getattr(response, "model_dump", None)) else {}
        if not isinstance(raw, dict):
            raw = {}
        if tool_calls:
            raw["tool_calls"] = tool_calls
        finish_reason = getattr(choice, "finish_reason", None)

        return LLMResponse(
            content=getattr(message, "content", None) or "",
            model=getattr(response, "model", model) or model,
            usage=self._extract_usage(getattr(response, "usage", None)),
            stop_reason=finish_reason if isinstance(finish_reason, str) else None,
            raw=raw,
        )

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Create a streaming chat completion."""
        config = config or CompletionConfig()
        request_kwargs = self._build_request_kwargs(messages, model, config, tools, stream=True)
        response = await self.client.chat.completions.create(**request_kwargs)

        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.delta

            if content := (getattr(delta, "content", None) or ""):
                yield StreamChunk(content=content, is_final=False)

            if tool_calls := self._extract_tool_calls(getattr(delta, "tool_calls", None)):
                yield StreamChunk(content="", is_final=False, raw={"tool_calls": tool_calls})

            if finish_reason := getattr(choice, "finish_reason", None):
                yield StreamChunk(content="", is_final=True, stop_reason=finish_reason)
                return

        yield StreamChunk(content="", is_final=True)

    def _build_request_kwargs(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig,
        tools: list[dict[str, Any]] | None,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self.convert_messages(messages),
            "max_tokens": config.max_tokens,
        }
        if stream:
            kwargs["stream"] = True
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.stop_sequences:
            kwargs["stop"] = config.stop_sequences
        if tools:
            kwargs["tools"] = tools
        return kwargs

    @classmethod
    def _extract_usage(cls, usage: Any) -> Usage | None:
        if usage is None:
            return None
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", None) or (input_tokens + output_tokens)
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)

    @classmethod
    def _extract_tool_calls(cls, tool_calls: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for tc in tool_calls or []:
            function = getattr(tc, "function", None)
            result.append(
                {
                    "id": getattr(tc, "id", None),
                    "type": getattr(tc, "type", "function") or "function",
                    "function": {
                        "name": getattr(function, "name", None) if function is not None else None,
                        "arguments": getattr(function, "arguments", "") if function is not None else "",
                    },
                }
            )
        return result

    @staticmethod
    def _normalise_tool_call_for_openai(tool_call: dict[str, Any]) -> dict[str, Any]:
        tc = dict(tool_call)
        function = dict(tc.get("function", {}))
        arguments = function.get("arguments", "")
        if isinstance(arguments, (dict, list)):
            function["arguments"] = json.dumps(arguments)
        elif arguments is None:
            function["arguments"] = "{}"
        tc["function"] = function
        tc.setdefault("type", "function")
        return tc

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified messages into the documented OpenAI chat format."""
        converted: list[dict[str, Any]] = []
        for msg in messages:
            item: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
            if msg.role == "tool":
                if msg.tool_call_id:
                    item["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    item["name"] = msg.name
            elif msg.role == "assistant":
                tool_calls = getattr(msg, "_tool_calls", None) or msg.metadata.get("_tool_calls")
                if tool_calls:
                    item["tool_calls"] = [self._normalise_tool_call_for_openai(tc) for tc in tool_calls]
            converted.append(item)
        return converted


# Alias for backwards compatibility.
OpenAIProvider = OpenAICompatibleProvider


__all__ = ["OpenAICompatibleProvider", "OpenAIProvider"]
