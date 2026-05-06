"""Google Gemini provider implementation."""

from __future__ import annotations

import os
import time
from typing import Any, AsyncIterator

from yom.providers.base import BaseProvider, CompletionConfig, LLMResponse, Message, StreamChunk, Usage


class GoogleProvider(BaseProvider):
    """Google Gemini provider using the official Google SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def client(self) -> Any:
        """Get or create cached client."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._get_api_key())
        return self._client

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert unified Message list to Google format."""
        contents = []
        for msg in messages:
            if msg.role == "system":
                continue  # System messages handled separately
            parts = [{"text": msg.content}]
            contents.append({
                "role": msg.role,
                "parts": parts,
            })
        return contents

    def _get_api_key(self) -> str:
        api_key = self._api_key
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is required")
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
                    if "rate_limit" in str(exc).lower() or "429" in str(exc):
                        wait_time = (2 ** attempt) * 1.0
                        time.sleep(wait_time)
                        continue
                    if "500" in str(exc) or "502" in str(exc) or "503" in str(exc):
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
        """Send completion request to Google Gemini."""
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "Google Gemini support requires installing 'google-genai' package: pip install google-genai"
            ) from exc

        config = config or CompletionConfig()

        system_instruction = ""
        google_contents = []
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                google_contents.append({
                    "role": msg.role,
                    "parts": [{"text": msg.content}],
                })

        gemini_model = model
        if not gemini_model.startswith("models/"):
            gemini_model = f"models/{gemini_model}"

        async def make_request():
            request_kwargs: dict[str, Any] = {
                "model": gemini_model,
                "contents": google_contents,
            }
            if system_instruction:
                request_kwargs["system_instruction"] = {"parts": [{"text": system_instruction}]}
            config_dict = {}
            if config.temperature:
                config_dict["temperature"] = config.temperature
            if config.max_tokens:
                config_dict["max_output_tokens"] = config.max_tokens
            if config_dict:
                request_kwargs["config"] = config_dict
            return await self.client.aio.models.generate_content(**request_kwargs)

        try:
            response = await self._retry_request(make_request, config)
        except Exception as exc:
            raise RuntimeError(f"Google Gemini request failed after {config.max_retries} retries: {exc}") from exc

        text = ""
        for candidate in response.candidates:
            if hasattr(candidate, "content") and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text

        stop_reason = None
        if response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "finish_reason"):
                stop_reason = str(candidate.finish_reason)

        usage = None
        if hasattr(response, "usage_metadata"):
            usage = Usage(
                input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0),
                output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0),
                total_tokens=getattr(response.usage_metadata, "total_token_count", 0),
            )

        raw = {}
        if hasattr(response, "model_dump"):
            raw = response.model_dump()
        elif hasattr(response, "to_dict"):
            raw = response.to_dict()

        return LLMResponse(
            content=text,
            model=model,
            usage=usage,
            stop_reason=stop_reason,
            raw=raw,
        )

    async def stream(
        self,
        messages: list[Message],
        model: str,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,  # type: ignore[override]
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from Google Gemini."""
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "Google Gemini support requires installing 'google-genai' package: pip install google-genai"
            ) from exc

        config = config or CompletionConfig()

        client = genai.Client(api_key=self._get_api_key())

        system_instruction = ""
        google_contents = []
        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                google_contents.append({
                    "role": msg.role,
                    "parts": [{"text": msg.content}],
                })

        gemini_model = model
        if not gemini_model.startswith("models/"):
            gemini_model = f"models/{gemini_model}"

        request_kwargs: dict[str, Any] = {
            "model": gemini_model,
            "contents": google_contents,
            "config": {"temperature": config.temperature} if config.temperature else {},
        }
        if system_instruction:
            request_kwargs["system_instruction"] = {"parts": [{"text": system_instruction}]}

        response = await client.aio.models.generate_content_stream(**request_kwargs)

        async for chunk in response:
            if chunk.candidates:
                candidate = chunk.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield StreamChunk(
                                content=part.text,
                                is_final=False,
                            )

        yield StreamChunk(content="", is_final=True)
