"""Runtime factory functions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from yom.models import AgentState
from yom.runtime.config import RuntimeSettings
from yom.runtime.deps import RuntimeDeps
from yom.runtime.runtime import AgentRuntime, StandaloneRuntime
from yom.session import FileSessionBackend, InMemorySessionBackend
from yom.context import ContextConfig, ContextManager, create_token_counter
from yom.logging_config import setup_logging


def build_runtime(
    settings: RuntimeSettings,
    deps: RuntimeDeps | None = None,
) -> AgentRuntime:
    """
    Build an AgentRuntime from RuntimeSettings.

    Args:
        settings: RuntimeSettings configuration
        deps: Optional RuntimeDeps (created from settings if None)
    """
    settings.validate()

    if settings.log_level:
        setup_logging(level=settings.log_level)

    if deps is None:
        deps = _build_default_deps(settings)

    return StandaloneRuntime(deps=deps, settings=settings)


def _build_default_deps(settings: RuntimeSettings) -> RuntimeDeps:
    """Build default dependencies from settings."""
    session_backend = settings.session_backend
    if session_backend is None:
        session_backend = FileSessionBackend()

    context_manager = None
    if settings.max_context_tokens is not None or settings.context_config is not None:
        from yom.context import ContextConfig, ContextManager
        config = settings.context_config or ContextConfig()
        if settings.max_context_tokens is not None:
            config.max_tokens = settings.max_context_tokens
        context_manager = ContextManager(config)

    return RuntimeDeps(
        session_backend=session_backend,
        tool_registry=None,
        context_manager=context_manager,
    )


def build_runtime_from_yaml(
    path: str | Path,
    overrides: dict | None = None,
) -> AgentRuntime:
    """
    Build runtime from YAML config file.

    Args:
        path: Path to YAML config file
        overrides: Optional dict to patch specific values
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    config = yaml.safe_load(path.read_text()) or {}

    if overrides:
        config = _deep_merge(config, overrides)

    if "session" in config:
        session_config = config["session"]
        backend_type = session_config.get("backend", "file")
        if backend_type == "file":
            config["session_backend"] = FileSessionBackend(
                base_dir=Path(session_config.get("path", "./sessions"))
            )
        elif backend_type == "memory":
            config["session_backend"] = InMemorySessionBackend()

    if "tools" in config:
        tools = []
        for tool_spec in config["tools"]:
            if isinstance(tool_spec, dict):
                tools.append(tool_spec)
        config["tools"] = tools

    settings = RuntimeSettings(**config)
    return build_runtime(settings)


def build_runtime_from_env(
    prefix: str = "AGENT_",
    required: list[str] | None = None,
) -> AgentRuntime:
    """
    Build runtime from environment variables.

    AGENT_RUNTIME_ID, AGENT_SYSTEM_PROMPT, etc.
    """
    required = required or ["RUNTIME_ID", "SYSTEM_PROMPT"]

    missing = [k for k in required if not os.getenv(f"{prefix}{k}")]
    if missing:
        raise ValueError(f"Missing required env vars: {missing}")

    settings = RuntimeSettings(
        runtime_id=os.getenv(f"{prefix}RUNTIME_ID", ""),
        system_prompt=os.getenv(f"{prefix}SYSTEM_PROMPT", ""),
        default_model=os.getenv(f"{prefix}DEFAULT_MODEL"),
        session_backend=InMemorySessionBackend(),
    )

    return build_runtime(settings)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result