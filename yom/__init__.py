"""yom: Configurable, installable agent runtime."""

from yom.agent import Agent
from yom.runtime import (
    AgentRuntime,
    RuntimeSettings,
    DEFAULT_SYSTEM_PROMPT,
    build_runtime,
    build_runtime_from_yaml,
    build_runtime_from_env,
    RuntimeDeps,
    SessionManager,
)
from yom.runtime.runtime import StandaloneRuntime
from yom.tools import Tool, ToolResult, tool, ToolRegistry, CORE_TOOLS
from yom.models import AgentState, Message, RuntimeRunResult
from yom.session import SessionBackend, FileSessionBackend, InMemorySessionBackend
from yom.hooks import HookRegistry, HookResult, block, allow, global_hooks, HOOK_NAMES
from yom.skills import Skill, LoadedSkills, load_skills, format_skills_for_prompt
from yom.providers import (
    LLMResponse,
    CompletionConfig,
    Message,
    StreamChunk,
    Usage,
    BaseProvider,
    ProviderFactory,
    create_provider,
    infer_provider,
    get_api_key,
    AnthropicProvider,
    OpenAIProvider,
    GoogleProvider,
)

__version__ = "0.1.0"

__all__ = [
    # Agent
    "Agent",
    # Runtime
    "AgentRuntime",
    "StandaloneRuntime",
    "DEFAULT_SYSTEM_PROMPT",
    "RuntimeSettings",
    "RuntimeDeps",
    "SessionManager",
    "build_runtime",
    "build_runtime_from_yaml",
    "build_runtime_from_env",
    # Tools
    "Tool",
    "ToolResult",
    "ToolRegistry",
    "tool",
    "CORE_TOOLS",
    # Models
    "AgentState",
    "Message",
    "RuntimeRunResult",
    # Session
    "SessionBackend",
    "FileSessionBackend",
    "InMemorySessionBackend",
    # Hooks
    "HookRegistry",
    "HookResult",
    "block",
    "allow",
    "global_hooks",
    "HOOK_NAMES",
    # Skills
    "Skill",
    "LoadedSkills",
    "load_skills",
    "format_skills_for_prompt",
    # Providers
    "LLMResponse",
    "CompletionConfig",
    "Message",
    "StreamChunk",
    "Usage",
    "BaseProvider",
    "ProviderFactory",
    "create_provider",
    "infer_provider",
    "get_api_key",
    "AnthropicProvider",
    "OpenAIProvider",
    "GoogleProvider",
]

try:
    from yom.fastapi import AgentRouter, create_agent_router, create_agent_app
    __all__.extend(["AgentRouter", "create_agent_router", "create_agent_app"])
except ImportError:
    pass

try:
    from yom.runtime.integration import (
        YomAgentRuntime,
        create_yom_agent_runtime,
    )
    __all__.extend(["YomAgentRuntime", "create_yom_agent_runtime"])
except ImportError:
    pass