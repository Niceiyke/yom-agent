"""LLM Providers for yom.

## Quick Start

```python
from yom import Agent
from yom.providers import create_provider

# Default: OpenAI
agent = Agent()

# Explicit OpenAI
agent = Agent(provider="openai", model="gpt-4o")

# Anthropic
agent = Agent(provider="anthropic", model="claude-3-5-sonnet-latest")

# Google
agent = Agent(provider="google", model="gemini-2.0-flash")

# Ollama (local)
agent = Agent(
    provider="openai",
    base_url="http://localhost:11434/v1",
    model="llama3",
)
```

## OpenAI-Compatible

Any server that implements the OpenAI chat completions API works:

| Server | Base URL |
|--------|----------|
| OpenAI | https://api.openai.com/v1 |
| Ollama | http://localhost:11434/v1 |
| LM Studio | http://localhost:1234/v1 |
| Groq | https://api.groq.com/openai/v1 |
| Fireworks | https://api.fireworks.ai/v1 |
| Together AI | https://api.together.xyz/v1 |

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GOOGLE_API_KEY` - Google API key

## Validation

Enable response validation with `YOM_VALIDATE=1` or `YOM_DEBUG=1`:

```bash
YOM_VALIDATE=1 python my_agent.py
```

This catches format inconsistencies in responses.
"""

from yom.providers.base import (
    BaseProvider,
    CompletionConfig,
    LLMResponse,
    Message,
    StreamChunk,
    Usage,
)
from yom.providers.factory import (
    AnthropicCompatibleProvider,
    GoogleCompatibleProvider,
    OpenAICompatibleProvider,
    create_provider,
)
from yom.providers.validation import (
    ENABLE_VALIDATION,
    ValidationError,
    validate_anthropic_response,
    validate_google_response,
    validate_message_format,
    validate_openai_response,
)

__all__ = [
    # Base types
    "BaseProvider",
    "CompletionConfig",
    "LLMResponse",
    "Message",
    "StreamChunk",
    "Usage",
    # Factory
    "create_provider",
    # Providers
    "OpenAICompatibleProvider",
    "AnthropicCompatibleProvider",
    "GoogleCompatibleProvider",
    # Validation
    "ValidationError",
    "validate_openai_response",
    "validate_anthropic_response",
    "validate_google_response",
    "validate_message_format",
    "ENABLE_VALIDATION",
]
