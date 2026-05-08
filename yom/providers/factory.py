"""Provider factory for yom.

Simple factory for creating LLM providers. No magic - just pass what you need.

## Supported Providers

| Provider | API | Models |
|----------|-----|--------|
| `openai` | OpenAI-compatible | gpt-4o, gpt-4-turbo, o1, etc. |
| `anthropic` | Anthropic-compatible | claude-3-5-sonnet, MiniMax-M2.7, etc. |
| `google` | Google AI | gemini-2.0-flash, gemini-pro, etc. |

## Quick Start

```python
from yom.providers import create_provider

# OpenAI
provider = create_provider(provider="openai", model="gpt-4o")

# Anthropic (Claude)
provider = create_provider(provider="anthropic", model="claude-3-5-sonnet-latest")

# Google
provider = create_provider(provider="google", model="gemini-2.0-flash")

# OpenAI-compatible (any server!)
provider = create_provider(
    provider="openai",  # or omit - it's the default
    model="llama3",
    base_url="http://localhost:11434/v1",  # Ollama
)

# MiniMax (uses Anthropic-compatible API)
provider = create_provider(model="MiniMax-M2.7")
# Or explicitly:
provider = create_provider(
    provider="anthropic",
    model="MiniMax-M2.7",
    base_url="https://api.minimax.io/anthropic",
)
```

## OpenAI-Compatible Servers

The `openai` provider works with ANY OpenAI-compatible API:

- **OpenAI**: https://api.openai.com/v1
- **Ollama**: http://localhost:11434/v1
- **LM Studio**: http://localhost:1234/v1
- **Groq**: https://api.groq.com/openai/v1
- **Fireworks**: https://api.fireworks.ai/v1
- **Together AI**: https://api.together.xyz/v1
- **vLLM**: http://localhost:8000/v1
- **Azure OpenAI**: (use Azure-specific SDK)

## MiniMax

MiniMax provides an Anthropic-compatible API at `https://api.minimax.io/anthropic`.
Auto-detected when model name starts with "minimax":

```python
provider = create_provider(model="MiniMax-M2.7")
# Sets:
#   provider="anthropic"
#   base_url="https://api.minimax.io/anthropic"
```

## Environment Variables

| Variable | Provider | Notes |
|----------|----------|-------|
| `OPENAI_API_KEY` | openai | Default for OpenAI |
| `ANTHROPIC_API_KEY` | anthropic | Anthropic/MiniMax API key |
| `MINIMAX_API_KEY` | anthropic | Alias for MiniMax |
| `GOOGLE_API_KEY` | google | Required for Gemini |

## Custom Base URL

```python
# Connect to Ollama running locally
provider = create_provider(
    provider="openai",
    model="llama3",
    base_url="http://localhost:11434/v1",
)

# Connect to MiniMax explicitly
provider = create_provider(
    provider="anthropic",
    model="MiniMax-M2.7",
    base_url="https://api.minimax.io/anthropic",
    api_key="your-minimax-key",
)
```
"""

from __future__ import annotations

import os

from yom.providers.anthropic import AnthropicCompatibleProvider
from yom.providers.base import BaseProvider
from yom.providers.google import GoogleCompatibleProvider
from yom.providers.openai import OpenAICompatibleProvider

# Default API URLs
DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": None,  # Uses Google's default
}

# MiniMax Anthropic-compatible endpoint
MINIMAX_ANTHROPIC_URL = "https://api.minimax.io/anthropic"

# Env vars to check
API_KEY_VARS = {
    "openai": ["OPENAI_API_KEY", "MINIMAX_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY", "MINIMAX_API_KEY"],
    "google": ["GOOGLE_API_KEY"],
}


def create_provider(
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseProvider:
    """Create an LLM provider.
    
    Args:
        model: Model name (e.g., "gpt-4o", "MiniMax-M2.7")
        provider: Provider type - "openai", "anthropic", or "google"
                   Auto-detected from model name if not specified.
        api_key: API key. Falls back to environment variables.
        base_url: Custom API URL. Useful for proxies or local servers.
                  Only used for "openai" and "anthropic" providers.
    
    Returns:
        Provider instance
        
    Examples:
        # Auto-detect from model name
        p = create_provider(model="MiniMax-M2.7")
        
        # OpenAI (default)
        p = create_provider(model="gpt-4o")
        
        # Anthropic (Claude or MiniMax)
        p = create_provider(provider="anthropic", model="claude-3-5-sonnet-latest")
        
        # Google
        p = create_provider(provider="google", model="gemini-2.0-flash")
        
        # Ollama (OpenAI-compatible)
        p = create_provider(model="llama3", base_url="http://localhost:11434/v1")
    """
    # Auto-detect provider from model name
    if provider is None and model:
        model_lower = model.lower()
        if model_lower.startswith("minimax"):
            provider = "anthropic"  # MiniMax uses Anthropic-compatible API
            if base_url is None:
                base_url = MINIMAX_ANTHROPIC_URL
        elif "claude" in model_lower:
            provider = "anthropic"
        elif "gemini" in model_lower:
            provider = "google"
        else:
            provider = "openai"  # Default
    elif provider is None:
        provider = "openai"
    
    # Get API key from env if not provided
    if api_key is None:
        # Check provider-specific env vars
        for var in API_KEY_VARS.get(provider, []):
            key = os.environ.get(var)
            if key:
                api_key = key
                break
        # Also check MINIMAX_API_KEY for Anthropic (MiniMax uses this)
        if provider == "anthropic" and api_key is None:
            api_key = os.environ.get("MINIMAX_API_KEY")
    
    # Create provider based on type. Providers receive base_url/api_key directly;
    # avoid mutating process environment so multiple providers can coexist.
    if provider == "anthropic":
        return AnthropicCompatibleProvider(api_key=api_key, base_url=base_url)
    
    elif provider == "google":
        return GoogleCompatibleProvider(api_key=api_key)
    
    else:
        # Default to OpenAI-compatible
        # base_url determines the actual server
        effective_base_url = base_url or DEFAULT_BASE_URLS.get("openai", "https://api.openai.com/v1")
        return OpenAICompatibleProvider(
            base_url=effective_base_url,
            api_key=api_key,
        )


__all__ = [
    "create_provider",
    "OpenAICompatibleProvider",
    "AnthropicCompatibleProvider",
    "GoogleCompatibleProvider",
]