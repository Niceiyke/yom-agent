"""Anthropic Messages provider.

Targets Anthropic's documented Messages API. Compatible Anthropic-style
providers can be used by changing ``model`` and ``base_url``.
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


class AnthropicCompatibleProvider(BaseProvider):
    """Provider for Anthropic-compatible Messages APIs."""

    DEFAULT_BASE_URL = "https://api.anthropic.com"
    ENV_API_KEYS = ("ANTHROPIC_API_KEY", "MINIMAX_API_KEY", "API_KEY")

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._default_headers = default_headers
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def client(self) -> Any:
        """Return a cached official Anthropic async client."""
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(
                api_key=self._get_api_key(),
                base_url=self._base_url,
                timeout=self._timeout,
                default_headers=self._default_headers,
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
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

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
        if code in {408, 409, 429, 529} or (code is not None and code >= 500):
            return True
        text = str(exc).lower()
        return any(marker in text for marker in ("rate limit", "overloaded", "timeout", "temporar"))

    async def _retry_request(self, request_fn: Callable[[], Awaitable[Any]], config: CompletionConfig) -> Any:
        last_error: Exception | None = None
        for attempt in range(config.max_retries + 1):
            try:
                return await request_fn()
            except Exception as exc:
                last_error = exc
                if attempt >= config.max_retries or not self._is_retryable(exc):
                    break
                await asyncio.sleep(min(30.0, 0.5 * (2**attempt)))
        raise last_error if last_error else RuntimeError("Anthropic request failed")

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Create a non-streaming Anthropic message."""
        config = config or CompletionConfig()
        anthropic_messages, system = self._convert_messages_and_system(messages)
        request_kwargs = self._build_request_kwargs(anthropic_messages, system, model, config, tools)

        try:
            response = await self._retry_request(
                lambda: self.client.messages.create(**request_kwargs),
                config,
            )
        except Exception as exc:
            raise RuntimeError(f"Anthropic request failed: {exc}") from exc

        content_blocks = list(getattr(response, "content", []) or [])
        text = "".join(
            getattr(block, "text", "")
            for block in content_blocks
            if (block.get("type") if isinstance(block, dict) else getattr(block, "type", None)) == "text"
        )
        tool_calls = self._extract_tool_calls(content_blocks)
        raw = {
            "content": content_blocks,
            "model": getattr(response, "model", model) or model,
            "stop_reason": getattr(response, "stop_reason", None),
        }
        if tool_calls:
            raw["tool_calls"] = tool_calls

        return LLMResponse(
            content=text,
            model=getattr(response, "model", model) or model,
            usage=self._extract_usage(getattr(response, "usage", None)),
            stop_reason=getattr(response, "stop_reason", None),
            raw=raw,
        )

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Create a streaming Anthropic message."""
        config = config or CompletionConfig()
        anthropic_messages, system = self._convert_messages_and_system(messages)
        request_kwargs = self._build_request_kwargs(anthropic_messages, system, model, config, tools)

        async with self.client.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) == "text_delta":
                        yield StreamChunk(content=getattr(delta, "text", ""), is_final=False)
                    elif getattr(delta, "type", None) == "input_json_delta":
                        yield StreamChunk(
                            content="",
                            is_final=False,
                            raw={"tool_input_delta": getattr(delta, "partial_json", "")},
                        )
                elif event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", None) == "tool_use":
                        yield StreamChunk(
                            content="",
                            is_final=False,
                            raw={
                                "tool_calls": [
                                    {
                                        "id": getattr(block, "id", None),
                                        "type": "function",
                                        "function": {
                                            "name": getattr(block, "name", None),
                                            "arguments": getattr(block, "input", {}) or {},
                                        },
                                    }
                                ]
                            },
                        )
                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    if stop_reason := getattr(delta, "stop_reason", None):
                        yield StreamChunk(content="", is_final=True, stop_reason=stop_reason)
                        return

        yield StreamChunk(content="", is_final=True)

    def _build_request_kwargs(
        self,
        messages: list[dict[str, Any]],
        system: str | list[dict[str, Any]] | None,
        model: str,
        config: CompletionConfig,
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": config.max_tokens,
        }
        if system:
            kwargs["system"] = system
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.top_p is not None:
            kwargs["top_p"] = config.top_p
        if config.stop_sequences:
            kwargs["stop_sequences"] = config.stop_sequences
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
        return kwargs

    @classmethod
    def _extract_usage(cls, usage: Any) -> Usage | None:
        if usage is None:
            return None
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        # Some APIs include cache token fields; keep total conservative/visible.
        total_tokens = input_tokens + output_tokens
        return Usage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)

    @classmethod
    def _extract_tool_calls(cls, content_blocks: list[Any]) -> list[dict[str, Any]]:
        tool_calls: list[dict[str, Any]] = []
        for block in content_blocks:
            block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if block_type != "tool_use":
                continue
            tool_calls.append(
                {
                    "id": block.get("id") if isinstance(block, dict) else getattr(block, "id", None),
                    "type": "function",
                    "function": {
                        "name": block.get("name") if isinstance(block, dict) else getattr(block, "name", None),
                        "arguments": block.get("input") if isinstance(block, dict) else getattr(block, "input", {}),
                    },
                }
            )
        return tool_calls

    @staticmethod
    def _as_anthropic_tool_input(arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str) and arguments.strip():
            try:
                parsed = json.loads(arguments)
                return parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                return {"value": arguments}
        return {}

    @classmethod
    def _tool_call_to_block(cls, tool_call: dict[str, Any]) -> dict[str, Any]:
        function = tool_call.get("function", tool_call)
        return {
            "type": "tool_use",
            "id": tool_call.get("id") or tool_call.get("tool_call_id"),
            "name": function.get("name", ""),
            "input": cls._as_anthropic_tool_input(function.get("arguments", function.get("input", {}))),
        }

    @classmethod
    def _content_blocks_from_raw(cls, raw_content: Any) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if not isinstance(raw_content, list):
            return blocks
        for block in raw_content:
            if isinstance(block, dict):
                blocks.append(block)
            else:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    blocks.append({"type": "text", "text": getattr(block, "text", "")})
                elif block_type == "tool_use":
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": getattr(block, "id", None),
                            "name": getattr(block, "name", None),
                            "input": getattr(block, "input", {}) or {},
                        }
                    )
        return blocks

    def _convert_messages_and_system(
        self,
        messages: list[Message],
    ) -> tuple[list[dict[str, Any]], str | None]:
        converted: list[dict[str, Any]] = []
        system_parts: list[str] = []

        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    system_parts.append(msg.content)
                continue

            if msg.role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or "",
                            }
                        ],
                    }
                )
                continue

            if msg.role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                content_blocks.extend(self._content_blocks_from_raw(msg.metadata.get("_raw_content")))

                if not content_blocks and msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})

                tool_calls = getattr(msg, "_tool_calls", None) or msg.metadata.get("_tool_calls")
                for tool_call in tool_calls or []:
                    block = self._tool_call_to_block(tool_call)
                    if block.get("id") and not any(b.get("type") == "tool_use" and b.get("id") == block["id"] for b in content_blocks):
                        content_blocks.append(block)

                converted.append({"role": "assistant", "content": content_blocks or msg.content or ""})
                continue

            # Anthropic only accepts user/assistant in messages. Unknown roles become user.
            role = msg.role if msg.role in {"user", "assistant"} else "user"
            converted.append({"role": role, "content": msg.content or ""})

        return converted, "\n\n".join(system_parts) if system_parts else None

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI function tool schema to Anthropic tool schema."""
        converted: list[dict[str, Any]] = []
        for tool in tools:
            function = tool.get("function", tool)
            converted.append(
                {
                    "name": function.get("name", ""),
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified messages into Anthropic ``messages`` format.

        System messages are intentionally omitted here because Anthropic accepts
        them through the top-level ``system`` request field.
        """
        converted, _ = self._convert_messages_and_system(messages)
        return converted


# Alias for backwards compatibility.
AnthropicProvider = AnthropicCompatibleProvider


__all__ = ["AnthropicCompatibleProvider", "AnthropicProvider"]
