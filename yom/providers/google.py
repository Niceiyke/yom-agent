"""Google-compatible provider for yom.

Works with Google's Gemini models via the Google AI API.

Usage:
    provider = GoogleCompatibleProvider(api_key="...")
    
    # Or via factory
    provider = create_provider(
        provider="google",
        model="gemini-2.0-flash",
        api_key="...",
    )
"""

from __future__ import annotations

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


class GoogleCompatibleProvider(BaseProvider):
    """Google-compatible provider using the official Google GenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize Google-compatible provider.
        
        Args:
            api_key: Google API key. Defaults to GOOGLE_API_KEY env var.
            base_url: Custom API URL if needed.
        """
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "google-compatible"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from google.genai import AsyncClient
            self._client = AsyncClient(
                api_key=self._get_api_key(),
            )
        return self._client

    def _get_api_key(self) -> str:
        """Get API key from config or environment."""
        if self._api_key:
            return self._api_key
        for var in ["GOOGLE_API_KEY", "API_KEY"]:
            key = os.environ.get(var)
            if key:
                return key
        raise ValueError("GOOGLE_API_KEY environment variable is required")

    async def complete(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send completion request to Google."""
        config = config or CompletionConfig()

        # Convert messages to Google format
        google_messages = []
        for msg in messages:
            if msg.role == "system":
                google_messages.append({"role": "user", "parts": [{"text": f"System: {msg.content}"}]})
            elif msg.role == "tool":
                google_messages.append({
                    "role": "model",
                    "parts": [{
                        "functionResponse": {
                            "name": getattr(msg, "name", "unknown"),
                            "response": {"content": msg.content}
                        }
                    }]
                })
            elif getattr(msg, "_tool_calls", None):
                parts = []
                for tc in msg._tool_calls:
                    func = tc.get("function", {})
                    parts.append({
                        "functionCall": {
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "args": func.get("arguments", {}),
                        }
                    })
                google_messages.append({"role": "user", "parts": parts})
            else:
                google_messages.append({
                    "role": "model" if msg.role == "assistant" else "user",
                    "parts": [{"text": msg.content}]
                })

        request_kwargs: dict[str, Any] = {
            "model": model,
            "contents": google_messages,
        }
        if config.temperature:
            request_kwargs["config"] = {"temperature": config.temperature}
        if tools:
            request_kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await self.client.models.generate_content(**request_kwargs)
        except Exception as exc:
            raise RuntimeError(f"Google request failed: {exc}") from exc

        # Extract text
        text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text += part.text

        # Usage
        usage = None
        if hasattr(response, "usage_metadata"):
            usage = Usage(
                input_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
                total_tokens=response.usage_metadata.total_token_count,
            )

        result = LLMResponse(
            content=text,
            model=model,
            usage=usage,
            stop_reason=str(response.candidates[0].finish_reason) if response.candidates else None,
            raw={"response": response},
        )
        
        # Validate (disabled by default, enable with YOM_VALIDATE=1)
        from yom.providers.validation import validate_google_response, validate_message_format
        validate_message_format("google", google_messages)
        validate_google_response(result)
        
        return result

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from Google."""
        config = config or CompletionConfig()

        google_messages = []
        for msg in messages:
            if msg.role == "system":
                google_messages.append({"role": "user", "parts": [{"text": f"System: {msg.content}"}]})
            else:
                google_messages.append({
                    "role": "model" if msg.role == "assistant" else "user",
                    "parts": [{"text": msg.content}]
                })

        request_kwargs: dict[str, Any] = {
            "model": model,
            "contents": google_messages,
            "stream": True,
        }
        if config.temperature:
            request_kwargs["config"] = {"temperature": config.temperature}

        try:
            async for chunk in await self.client.models.generate_content_stream(**request_kwargs):
                for part in chunk.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        yield StreamChunk(content=part.text, is_final=False)
        except Exception as exc:
            yield StreamChunk(content=f"Error: {exc}", is_final=True)

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to Google format."""
        google_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            google_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "parameters": func.get("parameters", {}),
            })
        return {"function_declarations": google_tools}

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to Google format."""
        result = []
        for msg in messages:
            if msg.role == "system":
                continue  # Handled differently
            elif msg.role == "tool":
                result.append({
                    "role": "model",
                    "parts": [{
                        "functionResponse": {
                            "name": getattr(msg, "name", "unknown"),
                            "response": {"content": msg.content}
                        }
                    }]
                })
            elif getattr(msg, "_tool_calls", None):
                parts = []
                for tc in msg._tool_calls:
                    func = tc.get("function", {})
                    parts.append({
                        "functionCall": {
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "args": func.get("arguments", {}),
                        }
                    })
                result.append({"role": "user", "parts": parts})
            else:
                result.append({
                    "role": "model" if msg.role == "assistant" else "user",
                    "parts": [{"text": msg.content}]
                })
        return result

# Alias for backwards compatibility
GoogleProvider = GoogleCompatibleProvider


__all__ = ["GoogleCompatibleProvider", "GoogleProvider"]
