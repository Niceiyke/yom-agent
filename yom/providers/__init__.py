"""Unified LLM provider system for yom.

Providers:
- Anthropic: claude-*, MiniMax-*
- OpenAI: gpt-*, o1-*, mistral-*, llama-*
- Google: gemini-*

Usage:
    from yom.providers import create_provider, Message

    # Auto-detect provider from model
    provider = create_provider(model="claude-3-5-sonnet-latest")

    # Or explicit
    provider = create_provider(provider="openai", api_key="sk-...")

    # Complete
    response = await provider.complete(
        messages=[Message(role="user", content="Hello")],
        model="claude-3-5-sonnet-latest",
    )
    print(response.content)
"""

from yom.providers.base import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    Usage,
)
from yom.providers.anthropic import AnthropicProvider
from yom.providers.google import GoogleProvider
from yom.providers.openai import OpenAIProvider
from yom.providers.factory import (
    ProviderFactory,
    create_provider,
    get_api_key,
    infer_provider,
)
from yom.providers.local import (
    OllamaProvider,
    LMStudioProvider,
    OllamaLocalProvider,
    create_local_provider,
)
from yom.providers.nvidia import NVIDIAProvider

__all__ = [
    # Types
    "BaseProvider",
    "CompletionConfig",
    "LLMResponse",
    "Message",
    "StreamChunk",
    "Usage",
    # Cloud Providers
    "AnthropicProvider",
    "GoogleProvider",
    "OpenAIProvider",
    "NVIDIAProvider",
    # Local Providers
    "OllamaProvider",
    "LMStudioProvider",
    "OllamaLocalProvider",
    "create_local_provider",
    # Factory
    "ProviderFactory",
    "create_provider",
    "get_api_key",
    "infer_provider",
]
