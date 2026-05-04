"""Provider factory for creating and managing LLM providers."""

from __future__ import annotations

import os
from typing import Any

from yom.providers.anthropic import AnthropicProvider
from yom.providers.base import BaseProvider, CompletionConfig, LLMResponse, Message, StreamChunk
from yom.providers.google import GoogleProvider
from yom.providers.openai import OpenAIProvider


# Model prefix to provider mapping
MODEL_PREFIX_MAP = {
    "claude": "anthropic",
    "MiniMax": "openai",  # MiniMax uses OpenAI-compatible API
}

# Default base URLs for known providers
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "minimax": "https://api.minimax.io/v1",
}

# Standard environment variable names per provider
STANDARD_API_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "minimax": "MINIMAX_API_KEY",
}

# Additional env vars to check for OpenAI-compatible providers
OPENAI_COMPATIBLE_API_KEYS = ["OPENAI_API_KEY", "MINIMAX_API_KEY"]


def infer_provider(model: str) -> tuple[str, str | None]:
    """Infer provider name and special base_url from model string.

    Returns:
        (provider, base_url_override)

    Examples:
        "claude-3-5-sonnet-latest" -> ("anthropic", None)
        "gpt-4o" -> ("openai", None)
        "MiniMax-M2.7" -> ("openai", "https://api.minimax.io/v1")
    """
    model_lower = model.lower()

    # Check prefix map
    for prefix, provider in MODEL_PREFIX_MAP.items():
        if model_lower.startswith(prefix.lower()):
            if model_lower.startswith("minimax"):
                return provider, "https://api.minimax.io/v1"
            return provider, None

    # Check for known model patterns
    if "claude" in model_lower:
        return "anthropic", None
    if "gpt" in model_lower or "o1" in model_lower or "o3" in model_lower:
        return "openai", None
    if "gemini" in model_lower:
        return "google", None
    if "mistral" in model_lower:
        return "openai", None
    if "llama" in model_lower:
        return "openai", None

    # Default to OpenAI for unknown models (most common)
    return "openai", None


def get_api_key(provider: str, model: str | None = None) -> str | None:
    """Get API key for a provider from environment."""
    # Special handling for OpenAI-compatible providers
    if provider == "openai" or (model and model.lower().startswith("minimax")):
        for env_var in ["MINIMAX_API_KEY", "OPENAI_API_KEY"]:
            key = os.environ.get(env_var)
            if key:
                return key
        return None
    return os.environ.get(STANDARD_API_KEYS.get(provider, f"{provider.upper()}_API_KEY"))


def create_provider(
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseProvider:
    """Create a provider instance.

    Args:
        model: Model name (used to infer provider if not specified)
        provider: Explicit provider name (auto-detected if None)
        api_key: API key (from env if not specified)
        base_url: Custom base URL (for proxies, etc.)

    Returns:
        Provider instance

    Examples:
        # Auto-detect provider from model
        create_provider(model="claude-3-5-sonnet-latest")

        # Explicit provider
        create_provider(provider="anthropic", api_key="sk-...")

        # With custom base_url (e.g., proxy)
        create_provider(
            model="claude-3-5-sonnet-latest",
            api_key="sk-...",
            base_url="https://my-proxy.com/v1"
        )
    """
    if provider is None:
        if model is None:
            provider = "openai"  # Default
            inferred_base_url = None
        else:
            provider, inferred_base_url = infer_provider(model)
    else:
        inferred_base_url = None

    if api_key is None:
        api_key = get_api_key(provider, model)

    # Use inferred base_url for special cases, otherwise use provided or default
    effective_base_url = inferred_base_url or base_url or DEFAULT_BASE_URLS.get(provider)

    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, base_url=effective_base_url)
    elif provider == "openai":
        return OpenAIProvider(api_key=api_key, base_url=effective_base_url)
    elif provider == "google":
        return GoogleProvider(api_key=api_key, base_url=effective_base_url)
    else:
        # Default to OpenAI-compatible
        return OpenAIProvider(api_key=api_key, base_url=effective_base_url)


class ProviderFactory:
    """Factory for creating providers with shared configuration."""

    def __init__(
        self,
        default_model: str | None = None,
        default_provider: str | None = None,
        default_api_key: str | None = None,
        default_base_url: str | None = None,
    ):
        self.default_model = default_model
        self.default_provider = default_provider
        self.default_api_key = default_api_key
        self.default_base_url = default_base_url

    def create(
        self,
        model: str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> BaseProvider:
        """Create a provider with defaults applied."""
        return create_provider(
            model=model or self.default_model,
            provider=provider or self.default_provider,
            api_key=api_key or self.default_api_key,
            base_url=base_url or self.default_base_url,
        )

    async def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        config: CompletionConfig | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMResponse:
        """Create provider and complete."""
        p = self.create(model=model, provider=provider, api_key=api_key, base_url=base_url)
        return await p.complete(messages, model=model or self.default_model or "", config=config)

    async def stream(
        self,
        messages: list[Message],
        model: str | None = None,
        config: CompletionConfig | None = None,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> StreamChunk:
        """Create provider and stream."""
        p = self.create(model=model, provider=provider, api_key=api_key, base_url=base_url)
        return p.stream(messages, model=model or self.default_model or "", config=config)
