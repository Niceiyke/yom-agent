"""Local model provider for yom - Ollama support.

Usage:
    from yom.providers import create_provider

    # Auto-detect
    provider = create_provider(model="llama3", base_url="http://localhost:11434/v1")

    # Or use OllamaProvider directly
    from yom.providers.local import OllamaProvider
    provider = OllamaProvider(base_url="http://localhost:11434")
"""

from __future__ import annotations


from typing import Any, AsyncIterator

from yom.providers.base import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    Usage,
)


class OllamaProvider(BaseProvider):
    """Ollama local model provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        model: str = "llama3",
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or "ollama"  # Ollama doesn't need real key
        self._model = model
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def client(self) -> Any:
        """Get or create httpx client."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=120.0,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        return self._client

    def convert_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert messages to Ollama format."""
        result = []
        for msg in messages:
            role = msg.role
            if role == "assistant":
                role = "assistant"
            elif role == "tool":
                role = "tool"
            result.append({
                "role": role,
                "content": msg.content,
            })
        return result

    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send completion request to Ollama."""
        import httpx

        config = config or CompletionConfig()
        model = model or self._model

        ollama_messages = self.convert_messages(messages)

        request_data: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }

        # Add tools if provided (Ollama with tool support)
        if tools:
            request_data["tools"] = self._convert_tools(tools)

        try:
            response = await self.client.post("/chat/completions", json=request_data)
            response.raise_for_status()
            data = response.json()

            # Handle Ollama response format
            if "message" in data:
                content = data["message"].get("content", "")
                tool_calls = data["message"].get("tool_calls", [])
            elif "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                tool_calls = choice.get("message", {}).get("tool_calls", [])
            else:
                content = str(data)
                tool_calls = []

            # Extract usage if available
            usage = None
            if "usage" in data:
                usage = Usage(
                    input_tokens=data["usage"].get("prompt_tokens", 0),
                    output_tokens=data["usage"].get("completion_tokens", 0),
                    total_tokens=data["usage"].get("total_tokens", 0),
                )

            raw = {"data": data}

            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                stop_reason=data.get("done_reason", "stop"),
                raw=raw,
            )

        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream completion from Ollama."""
        import httpx

        config = config or CompletionConfig()
        model = model or self._model

        ollama_messages = self.convert_messages(messages)

        request_data: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
        }

        try:
            async with self.client.stream("POST", "/chat/completions", json=request_data) as response:
                response.raise_for_status()
                full_content = ""

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        line = line[6:]

                    if line == "[DONE]":
                        yield StreamChunk(content="", is_final=True)
                        return

                    try:
                        import json
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if "message" in data:
                        chunk = data["message"].get("content", "")
                        full_content += chunk
                        yield StreamChunk(content=chunk, is_final=False)
                    elif "choices" in data and len(data["choices"]) > 0:
                        chunk = data["choices"][0].get("delta", {}).get("content", "")
                        if chunk:
                            full_content += chunk
                            yield StreamChunk(content=chunk, is_final=False)

                yield StreamChunk(content="", is_final=True)

        except httpx.HTTPError as e:
            yield StreamChunk(content=f"Error: {e}", is_final=True)

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to Ollama format."""
        ollama_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                },
            })
        return ollama_tools


class LMStudioProvider(OllamaProvider):
    """LM Studio provider (Ollama-compatible API)."""

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        api_key: str | None = "lm-studio",
        model: str = "local-model",
    ):
        super().__init__(base_url=base_url, api_key=api_key, model=model)

    @property
    def provider_name(self) -> str:
        return "lmstudio"


class OllamaLocalProvider(OllamaProvider):
    """Native Ollama API provider (not OpenAI-compatible)."""

    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        config: CompletionConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send completion using native Ollama API."""
        import httpx

        config = config or CompletionConfig()
        model = model or self._model

        # Convert to Ollama chat format
        ollama_messages = []
        for msg in messages:
            role = msg.role
            if role == "assistant":
                role = "assistant"
            elif role == "tool":
                role = "tool"
            ollama_messages.append({
                "role": role,
                "content": msg.content,
            })

        request_data: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "num_predict": config.max_tokens,
            },
        }

        try:
            # Use /api/chat endpoint for native Ollama
            response = await self.client.post("/api/chat", json=request_data)
            response.raise_for_status()
            data = response.json()

            content = data.get("message", {}).get("content", "")

            return LLMResponse(
                content=content,
                model=model,
                usage=Usage(
                    input_tokens=data.get("prompt_eval_count", 0),
                    output_tokens=data.get("eval_count", 0),
                    total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                ),
                stop_reason="stop",
                raw={"data": data},
            )

        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama API request failed: {e}")


def create_local_provider(
    backend: str = "ollama",
    base_url: str | None = None,
    model: str = "llama3",
) -> BaseProvider:
    """Create a local model provider.

    Args:
        backend: Backend type ("ollama", "lmstudio", "ollama-native")
        base_url: API base URL
        model: Model name

    Returns:
        Provider instance
    """
    if backend == "ollama":
        url = base_url or "http://localhost:11434/v1"
        return OllamaProvider(base_url=url, model=model)
    elif backend == "lmstudio":
        url = base_url or "http://localhost:1234/v1"
        return LMStudioProvider(base_url=url, model=model)
    elif backend == "ollama-native":
        url = base_url or "http://localhost:11434"
        return OllamaLocalProvider(base_url=url, model=model)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'ollama', 'lmstudio', or 'ollama-native'")


__all__ = [
    "OllamaProvider",
    "LMStudioProvider",
    "OllamaLocalProvider",
    "create_local_provider",
]
