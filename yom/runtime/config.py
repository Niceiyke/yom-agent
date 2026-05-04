"""Runtime configuration types."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from yom.models import AgentState
    from yom.session.backends import SessionBackend
    from yom.tools import Tool
    from yom.tools.protocol import EventHook


@dataclass
class ModelConfig:
    """Per-model configuration."""

    temperature: float = 0.7
    top_p: float | None = None
    max_tokens: int | None = None
    stop_sequences: list[str] = field(default_factory=list)


@dataclass
class PromptTemplate:
    """System prompt template with variable substitution."""

    template: str
    name: str | None = None

    def render(self, vars: dict[str, str]) -> str:
        """Render template with provided variables."""
        result = self.template
        for key, value in vars.items():
            result = result.replace(f"{{{key}}}", value)
        return result


@dataclass
class RuntimeSettings:
    """Configuration for an AgentRuntime instance."""

    # === Identity ===
    runtime_id: str

    # === Prompt Configuration ===
    system_prompt: str | PromptTemplate = ""
    prompt_vars: dict[str, str] = field(default_factory=dict)
    max_turns: int = 50

    # === Model Configuration ===
    default_model: str | None = None
    provider: str | None = None  # Auto-detected from model if None
    api_key: str | None = None  # From env if None
    base_url: str | None = None  # For custom endpoints/proxies
    allowed_models: list[str] | None = None
    model_configs: dict[str, ModelConfig] = field(default_factory=dict)

    # === Tool Configuration ===
    tools: list[Tool | Callable] = field(default_factory=list)

    # === Session/Storage Configuration ===
    session_backend: SessionBackend | None = None
    session_ttl: int = 3600
    max_session_history: int | None = None

    # === Observability ===
    event_hooks: list[EventHook] = field(default_factory=list)
    log_level: str = "INFO"
    trace_enabled: bool = False

    # === Execution ===
    timeout: float = 120.0
    max_retries: int = 3

    def get_system_prompt(self) -> str:
        """Get resolved system prompt as string."""
        prompt = self.system_prompt
        if isinstance(prompt, PromptTemplate):
            prompt = prompt.render(self.prompt_vars)
        elif self.prompt_vars:
            result = prompt
            for key, value in self.prompt_vars.items():
                result = result.replace(f"{{{key}}}", value)
            prompt = result
        return prompt

    def validate(self) -> None:
        """Validate settings at build time."""
        if not self.runtime_id:
            raise ValueError("runtime_id is required")

        if self.system_prompt is None:
            raise ValueError("system_prompt is required")

        if self.allowed_models and self.default_model:
            if self.default_model not in self.allowed_models:
                raise ValueError(
                    f"default_model '{self.default_model}' not in allowed_models"
                )

        for tool in self.tools:
            if not hasattr(tool, "name") and not callable(tool):
                raise ValueError(f"Invalid tool: {tool}")