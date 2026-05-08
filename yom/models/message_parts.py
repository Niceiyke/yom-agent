"""Message part types for agent conversations."""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, cast

from typing_extensions import Annotated, Self, TypeAliasType

from pydantic import Discriminator


def _now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


T = TypeVar('T')


# ============================================================================
# Part Types
# ============================================================================

@dataclass(repr=False)
class BasePart(ABC):
    """Base class for all message parts."""
    
    @property
    @abstractmethod
    def part_kind(self) -> str:
        """Return the part type identifier."""
        raise NotImplementedError()
    
    def has_content(self) -> bool:
        """Return True if the part has non-empty content."""
        return True


@dataclass(repr=False)
class TextPart(BasePart):
    """A plain text response from a model."""

    content: str
    """The text content of the response."""

    id: str | None = None
    """Optional identifier of the text part."""

    provider_name: str | None = None
    """The name of the provider that generated the response."""

    provider_details: dict[str, Any] | None = None
    """Additional data returned by the provider."""

    part_kind: Literal['text'] = 'text'

    def has_content(self) -> bool:
        return bool(self.content)


@dataclass(repr=False)
class ThinkingPart(BasePart):
    """A thinking response from a model (reasoning/chain-of-thought)."""

    content: str
    """The thinking content of the response."""

    id: str | None = None
    """The identifier of the thinking part."""

    signature: str | None = None
    """The signature of the thinking (for providers that support it)."""

    provider_name: str | None = None
    """The name of the provider that generated the response."""

    provider_details: dict[str, Any] | None = None
    """Additional data returned by the provider."""

    part_kind: Literal['thinking'] = 'thinking'

    def has_content(self) -> bool:
        return bool(self.content)


@dataclass(repr=False)
class ToolCallPart(BasePart):
    """A tool call from a model."""

    tool_name: str
    """The name of the tool to call."""

    args: str | dict[str, Any] | None = None
    """The arguments to pass to the tool (JSON string or dict)."""

    tool_call_id: str | None = None
    """The tool call identifier."""

    id: str | None = None
    """Optional identifier separate from tool_call_id."""

    provider_name: str | None = None
    """The name of the provider that generated the response."""

    provider_details: dict[str, Any] | None = None
    """Additional data returned by the provider."""

    part_kind: Literal['tool_call'] = 'tool_call'

    def __post_init__(self):
        if self.tool_call_id is None:
            self.tool_call_id = f"call_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

    def args_as_dict(self, *, raise_if_invalid: bool = False) -> dict[str, Any]:
        """Return the arguments as a Python dictionary.
        
        Args:
            raise_if_invalid: If True, re-raise ValueError/AssertionError for malformed JSON.
                If False (default), returns {'INVALID_JSON': '<raw args>'} for bad JSON.
        """
        if not self.args:
            return {}
        if isinstance(self.args, dict):
            return self.args
        
        try:
            return json.loads(self.args)
        except json.JSONDecodeError as e:
            if raise_if_invalid:
                raise ValueError(f"Invalid JSON in tool arguments: {e}") from e
            return {'INVALID_JSON': self.args}


@dataclass(repr=False)
class ToolReturnPart(BasePart):
    """A tool return/result from executing a tool."""

    tool_name: str
    """The name of the tool that was called."""

    content: Any
    """The tool return content (can be any type including multimodal)."""

    tool_call_id: str | None = None
    """The tool call identifier."""

    outcome: Literal['success', 'failed', 'denied'] = 'success'
    """The outcome of the tool call."""

    metadata: Any = None
    """Additional data accessible by the application but not sent to the LLM."""

    timestamp: datetime = field(default_factory=_now)
    """The timestamp when the tool returned."""

    part_kind: Literal['tool_return'] = 'tool_return'

    def has_content(self) -> bool:
        """Check if there's actual content to return."""
        if self.content is None:
            return False
        if isinstance(self.content, str) and not self.content:
            return False
        return True


# ============================================================================
# Discriminated Union Types
# ============================================================================

ModelResponsePart = Annotated[
    TextPart | ToolCallPart | ThinkingPart | ToolReturnPart,
    Discriminator('part_kind'),
]
"""A message part returned by a model."""


# ============================================================================
# Model Request
# ============================================================================

@dataclass(repr=False)
class UserPromptPart(BasePart):
    """A user prompt part."""

    content: str | list[Any]
    """The content of the prompt."""

    timestamp: datetime = field(default_factory=_now)

    part_kind: Literal['user_prompt'] = 'user_prompt'

    def has_content(self) -> bool:
        if isinstance(self.content, str):
            return bool(self.content)
        return len(self.content) > 0


@dataclass(repr=False)
class RetryPromptPart(BasePart):
    """A retry prompt part shown to the model when validation fails."""

    content: Any
    """The error content (validation errors or error message)."""

    tool_name: str | None = None
    """The name of the tool that failed validation."""

    tool_call_id: str | None = None
    """The tool call ID that failed validation."""

    part_kind: Literal['retry_prompt'] = 'retry_prompt'


@dataclass(repr=False)
class ModelRequest:
    """A request message sent to the model."""

    parts: list[UserPromptPart | RetryPromptPart]
    """The parts of the model request."""

    role: Literal['user', 'developer'] = 'user'
    """The role for the request."""

    timestamp: datetime = field(default_factory=_now)
    """The timestamp when the request was created."""

    run_id: str | None = None
    """The unique identifier of the agent run."""

    conversation_id: str | None = None
    """The unique identifier of the conversation."""

    metadata: dict[str, Any] | None = None
    """Additional data accessible programmatically."""

    kind: Literal['request'] = 'request'
    """Message type identifier."""

    @property
    def messages(self) -> list[Any]:
        """Get messages as a list for compatibility."""
        return self.parts

    def user_prompt(self) -> str | None:
        """Get the user prompt content."""
        for part in self.parts:
            if isinstance(part, UserPromptPart):
                content = part.content
                if isinstance(content, str):
                    return content
        return None


@dataclass(repr=False)
class RequestUsage:
    """Token usage information for a request."""

    input_tokens: int = 0
    """Number of input tokens."""

    output_tokens: int = 0
    """Number of output tokens."""

    total_tokens: int = 0
    """Total tokens used."""

    details: dict[str, Any] = field(default_factory=dict)
    """Provider-specific usage details."""


@dataclass(repr=False)
class ModelResponse:
    """A response from a model."""

    parts: list[ModelResponsePart]
    """The parts of the model message."""

    usage: RequestUsage = field(default_factory=RequestUsage)
    """Usage information for the request."""

    model_name: str | None = None
    """The name of the model that generated the response."""

    timestamp: datetime = field(default_factory=_now)
    """The timestamp when the response was received."""

    kind: Literal['response'] = 'response'
    """Message type identifier."""

    provider_name: str | None = None
    """The name of the LLM provider."""

    provider_url: str | None = None
    """The base URL of the LLM provider."""

    provider_details: dict[str, Any] | None = None
    """Additional data returned by the provider."""

    provider_response_id: str | None = None
    """Request ID from the model provider."""

    finish_reason: str | None = None
    """Reason the model finished (normalized to OpenTelemetry values)."""

    run_id: str | None = None
    """The unique identifier of the agent run."""

    conversation_id: str | None = None
    """The unique identifier of the conversation."""

    metadata: dict[str, Any] | None = None
    """Additional data accessible programmatically."""

    @property
    def text(self) -> str | None:
        """Get the text content from the response."""
        texts: list[str] = []
        last_part: ModelResponsePart | None = None
        
        for part in self.parts:
            if isinstance(part, TextPart):
                if isinstance(last_part, TextPart):
                    texts[-1] += part.content
                else:
                    texts.append(part.content)
            last_part = part
        
        if not texts:
            return None
        return '\n\n'.join(texts)

    @property
    def thinking(self) -> str | None:
        """Get the thinking content from the response."""
        thinking_parts = [part.content for part in self.parts if isinstance(part, ThinkingPart)]
        if not thinking_parts:
            return None
        return '\n\n'.join(thinking_parts)

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        """Get all tool calls from the response."""
        return [part for part in self.parts if isinstance(part, ToolCallPart)]

    @property
    def tool_returns(self) -> list[ToolReturnPart]:
        """Get all tool returns from the response."""
        return [part for part in self.parts if isinstance(part, ToolReturnPart)]

    def text_or_raise(self) -> str:
        """Get text or raise if not available."""
        text = self.text
        if text is None:
            raise ValueError("No text content in response")
        return text

    def cost(self) -> dict[str, Any]:
        """Calculate the cost of the usage (placeholder for genai-prices integration)."""
        return {
            'input_tokens': self.usage.input_tokens,
            'output_tokens': self.usage.output_tokens,
            'total_tokens': self.usage.total_tokens,
        }


# ============================================================================
# Streaming Deltas
# ============================================================================

@dataclass(repr=False)
class TextPartDelta:
    """A partial update (delta) for a TextPart."""

    content: str
    """The incremental text content to add."""

    part_delta_kind: Literal['text'] = 'text'

    def apply(self, part: ModelResponsePart | TextPart) -> TextPart:
        """Apply this delta to create an updated TextPart."""
        if isinstance(part, TextPart):
            return TextPart(
                content=part.content + self.content,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        elif isinstance(part, TextPartDelta):
            return TextPart(
                content=part.content + self.content,
            )
        raise ValueError(f"Cannot apply TextPartDelta to {type(part)}")


@dataclass(repr=False)
class ThinkingPartDelta:
    """A partial update (delta) for a ThinkingPart."""

    content: str
    """The incremental thinking content to add."""

    part_delta_kind: Literal['thinking'] = 'thinking'

    def apply(self, part: ModelResponsePart | ThinkingPart) -> ThinkingPart:
        """Apply this delta to create an updated ThinkingPart."""
        if isinstance(part, ThinkingPart):
            return ThinkingPart(
                content=part.content + self.content,
                id=part.id,
                signature=part.signature,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        elif isinstance(part, ThinkingPartDelta):
            return ThinkingPart(
                content=part.content + self.content,
            )
        raise ValueError(f"Cannot apply ThinkingPartDelta to {type(part)}")


@dataclass(repr=False)
class ToolCallPartDelta:
    """A partial update (delta) for a ToolCallPart."""

    tool_name_delta: str | None = None
    """Incremental tool name (for streaming name changes)."""

    args_delta: str | None = None
    """Incremental arguments (JSON string being streamed)."""

    tool_call_id: str | None = None
    """The tool call ID."""

    part_delta_kind: Literal['tool_call'] = 'tool_call'

    def as_part(self) -> ToolCallPart | None:
        """Convert to a fully formed ToolCallPart if possible."""
        if self.tool_name_delta is not None:
            return ToolCallPart(
                tool_name=self.tool_name_delta,
                args=self.args_delta,
                tool_call_id=self.tool_call_id,
            )
        return None

    def apply(self, part: ModelResponsePart | ToolCallPart) -> ToolCallPart | ToolCallPartDelta:
        """Apply this delta to update or create a ToolCallPart."""
        if isinstance(part, ToolCallPart):
            tool_name = self.tool_name_delta or part.tool_name
            
            # Handle args merging
            existing_args = part.args or {}
            if isinstance(existing_args, str):
                try:
                    existing_args = json.loads(existing_args)
                except json.JSONDecodeError:
                    existing_args = {}
            
            new_args = existing_args
            if self.args_delta:
                if isinstance(self.args_delta, str):
                    try:
                        delta_dict = json.loads(self.args_delta)
                        if isinstance(delta_dict, dict):
                            new_args = {**existing_args, **delta_dict}
                    except json.JSONDecodeError:
                        new_args = str(existing_args) + self.args_delta
                elif isinstance(self.args_delta, dict):
                    new_args = {**existing_args, **self.args_delta}
            
            return ToolCallPart(
                tool_name=tool_name,
                args=new_args,
                tool_call_id=self.tool_call_id or part.tool_call_id,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        elif isinstance(part, ToolCallPartDelta):
            return ToolCallPartDelta(
                tool_name_delta=self.tool_name_delta or part.tool_name_delta,
                args_delta=(part.args_delta or '') + (self.args_delta or ''),
                tool_call_id=self.tool_call_id or part.tool_call_id,
            )
        raise ValueError(f"Cannot apply ToolCallPartDelta to {type(part)}")


ModelResponsePartDelta = Annotated[
    TextPartDelta | ThinkingPartDelta | ToolCallPartDelta,
    Discriminator('part_delta_kind'),
]
"""A partial update for a streaming model response."""


# ============================================================================
# Message Type Aliases
# ============================================================================

ModelMessage = Annotated[
    ModelRequest | ModelResponse,
    Discriminator('kind'),
]
"""A message in the conversation, either a request or response."""
