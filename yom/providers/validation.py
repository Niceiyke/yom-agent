"""Response validation for providers.

Validates responses match expected formats. Enable with YOM_DEBUG=1 or YOM_VALIDATE=1.
"""

from __future__ import annotations

import os


# Validation is disabled by default for performance
# Enable with YOM_VALIDATE=1 or YOM_DEBUG=1
ENABLE_VALIDATION = os.environ.get("YOM_VALIDATE", "0") == "1" or os.environ.get("YOM_DEBUG", "0") == "1"


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_openai_response(response: LLMResponse) -> None:
    """Validate OpenAI-compatible response format."""
    if not ENABLE_VALIDATION:
        return
    
    if not isinstance(response.content, str):
        raise ValidationError(f"OpenAI response.content must be str, got {type(response.content)}")
    
    # Check raw data has expected structure
    raw = response.raw or {}
    if "tool_calls" in raw:
        tool_calls = raw["tool_calls"]
        if not isinstance(tool_calls, list):
            raise ValidationError(f"tool_calls must be list, got {type(tool_calls)}")
        for i, tc in enumerate(tool_calls):
            if not isinstance(tc, dict):
                raise ValidationError(f"tool_call[{i}] must be dict, got {type(tc)}")
            if "function" not in tc:
                raise ValidationError(f"tool_call[{i}] missing 'function' key")
            func = tc["function"]
            if not isinstance(func, dict):
                raise ValidationError(f"tool_call[{i}].function must be dict, got {type(func)}")
            if "name" not in func:
                raise ValidationError(f"tool_call[{i}].function missing 'name'")


def validate_anthropic_response(response: LLMResponse) -> None:
    """Validate Anthropic response format."""
    if not ENABLE_VALIDATION:
        return
    
    # Anthropic returns text in content blocks
    raw = response.raw or {}
    content = raw.get("content", [])
    
    if not isinstance(content, list):
        raise ValidationError(f"Anthropic content must be list, got {type(content)}")
    
    for block in content:
        if not isinstance(block, dict):
            raise ValidationError(f"Anthropic content block must be dict, got {type(block)}")
        if "type" not in block:
            raise ValidationError("Anthropic content block missing 'type'")
        block_type = block["type"]
        if block_type not in ("text", "tool_use"):
            raise ValidationError(f"Unknown Anthropic block type: {block_type}")


def validate_google_response(response: LLMResponse) -> None:
    """Validate Google response format."""
    if not ENABLE_VALIDATION:
        return
    
    # Google returns candidates with parts
    raw = response.raw or {}
    
    if "response" in raw:
        resp = raw["response"]
        if hasattr(resp, "candidates"):
            for candidate in resp.candidates:
                if hasattr(candidate, "content"):
                    content = candidate.content
                    if hasattr(content, "parts"):
                        for part in content.parts:
                            if hasattr(part, "function_call"):
                                fc = part.function_call
                                if not hasattr(fc, "name") or not hasattr(fc, "args"):
                                    raise ValidationError("Google function_call missing name or args")


def validate_message_format(provider: str, messages: list[dict]) -> None:
    """Validate converted messages match provider format.
    
    Args:
        provider: Provider name (openai, anthropic, google)
        messages: Converted message dicts
    """
    if not ENABLE_VALIDATION:
        return
    
    for msg in messages:
        if not isinstance(msg, dict):
            raise ValidationError(f"Message must be dict, got {type(msg)}")
        
        if "role" not in msg:
            raise ValidationError(f"Message missing 'role': {msg}")
        
        if provider == "openai":
            _validate_openai_message(msg)
        elif provider == "anthropic":
            _validate_anthropic_message(msg)
        elif provider == "google":
            _validate_google_message(msg)


def _validate_openai_message(msg: dict) -> None:
    """Validate OpenAI message format."""
    role = msg.get("role")
    if role not in ("system", "user", "assistant", "tool"):
        raise ValidationError(f"Invalid OpenAI role: {role}")
    
    if role == "tool":
        if "tool_call_id" not in msg:
            raise ValidationError("OpenAI tool message missing 'tool_call_id'")
    
    if "tool_calls" in msg:
        tool_calls = msg["tool_calls"]
        if not isinstance(tool_calls, list):
            raise ValidationError("tool_calls must be list")
        for tc in tool_calls:
            if "function" not in tc:
                raise ValidationError("tool_call missing 'function'")
            func = tc["function"]
            if not isinstance(func.get("name"), str):
                raise ValidationError("tool_call.function.name must be string")


def _validate_anthropic_message(msg: dict) -> None:
    """Validate Anthropic message format."""
    role = msg.get("role")
    if role not in ("system", "user", "assistant"):
        raise ValidationError(f"Invalid Anthropic role: {role}")
    
    content = msg.get("content")
    if not isinstance(content, (str, list)):
        raise ValidationError(f"Anthropic content must be str or list, got {type(content)}")
    
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                raise ValidationError("Anthropic content block must be dict")
            if "type" not in block:
                raise ValidationError("Anthropic content block missing 'type'")


def _validate_google_message(msg: dict) -> None:
    """Validate Google message format."""
    role = msg.get("role")
    if role not in ("system", "user", "model"):
        raise ValidationError(f"Invalid Google role: {role}")
    
    if "parts" not in msg:
        raise ValidationError("Google message missing 'parts'")
    
    parts = msg["parts"]
    if not isinstance(parts, list):
        raise ValidationError("Google parts must be list")
    
    for part in parts:
        if not isinstance(part, dict):
            raise ValidationError("Google part must be dict")


# Import at bottom to avoid circular imports
from yom.providers.base import LLMResponse

__all__ = [
    "ValidationError",
    "validate_openai_response",
    "validate_anthropic_response",
    "validate_google_response",
    "validate_message_format",
    "ENABLE_VALIDATION",
]
