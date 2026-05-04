"""Runtime factory functions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Literal

import yaml

from yom.models import AgentState
from yom.runtime.config import RuntimeSettings
from yom.runtime.deps import RuntimeDeps
from yom.runtime.runtime import AgentRuntime, StandaloneRuntime
from yom.session import FileSessionBackend, InMemorySessionBackend


def build_runtime(
    settings: RuntimeSettings,
    deps: RuntimeDeps | None = None,
    mode: Literal["standalone", "yom_agent"] = "standalone",
) -> AgentRuntime:
    """
    Build an AgentRuntime from RuntimeSettings.

    Args:
        settings: RuntimeSettings configuration
        deps: Optional RuntimeDeps (created from settings if None)
        mode: "standalone" (pure Python, no LLM calls) or "yom_agent" (uses real LLM)
    """
    settings.validate()

    if deps is None:
        deps = _build_default_deps(settings)

    if mode == "yom_agent":
        return _build_yom_agent_runtime(settings, deps)
    return StandaloneRuntime(deps=deps, settings=settings)


def _build_yom_agent_runtime(
    settings: RuntimeSettings,
    deps: RuntimeDeps,
) -> "YomAgentRuntime":
    """Build a runtime that uses yom_agent internals."""
    try:
        from yom.runtime.integration import (
            YomAgentRuntime,
            IntegratedDeps,
            convert_yom_tools,
        )

        from coding_agent.tools.registry import ToolRegistry as CAToolRegistry
        from coding_agent.agent.session import SessionManager as CASessionManager, RuntimeSession
        from coding_agent.hooks.hooks import global_hooks

        ca_tool_registry = CAToolRegistry()

        # Convert and register agent-core tools into yom_agent registry
        tool_map, schemas = convert_yom_tools(settings.tools)
        for name, adapter in tool_map.items():
            ca_tool_registry.register(adapter.execute, adapter.schema)

        ca_session_manager = CASessionManager()
        ca_session = RuntimeSession()

        integrated_deps = IntegratedDeps(
            tool_registry=ca_tool_registry,
            session_manager=ca_session_manager,
            hooks=global_hooks,
            session=ca_session,
        )

        return YomAgentRuntime(deps=integrated_deps, settings=settings)
    except ImportError as e:
        raise ImportError(
            f"yom_agent not available. Install it or use mode='standalone'. Error: {e}"
        )


def _build_default_deps(settings: RuntimeSettings) -> RuntimeDeps:
    """Build default dependencies from settings."""
    session_backend = settings.session_backend
    if session_backend is None:
        session_backend = FileSessionBackend()

    return RuntimeDeps(
        session_backend=session_backend,
        tool_registry=None,
    )


def build_runtime_from_yaml(
    path: str | Path,
    overrides: dict | None = None,
    mode: Literal["standalone", "yom_agent"] = "standalone",
) -> AgentRuntime:
    """
    Build runtime from YAML config file.

    Args:
        path: Path to YAML config file
        overrides: Optional dict to patch specific values
        mode: "standalone" or "yom_agent"
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    config = yaml.safe_load(path.read_text()) or {}

    if overrides:
        config = _deep_merge(config, overrides)

    # Convert session backend string to actual backend
    if "session" in config:
        session_config = config["session"]
        backend_type = session_config.get("backend", "file")
        if backend_type == "file":
            config["session_backend"] = FileSessionBackend(
                base_dir=Path(session_config.get("path", "./sessions"))
            )
        elif backend_type == "memory":
            config["session_backend"] = InMemorySessionBackend()

    # Handle tools list (can contain dicts or import paths)
    if "tools" in config:
        tools = []
        for tool_spec in config["tools"]:
            if isinstance(tool_spec, dict):
                tools.append(tool_spec)
        config["tools"] = tools

    settings = RuntimeSettings(**config)
    return build_runtime(settings, mode=mode)


def build_runtime_from_env(
    prefix: str = "AGENT_",
    required: list[str] | None = None,
    mode: Literal["standalone", "yom_agent"] = "standalone",
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

    return build_runtime(settings, mode=mode)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result