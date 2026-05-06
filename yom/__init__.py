"""yom: Configurable, installable agent runtime.

Open source agent framework with tool calling, session management,
multi-provider LLM support, and plugin system.
"""

from yom.agent import Agent
from yom.agent_runtime import AgentRuntime, CoreRuntime, DEFAULT_SYSTEM_PROMPT
from yom.config import RuntimeSettings
from yom.deps import RuntimeDeps, SessionManager
from yom.factories import build_runtime, build_runtime_from_yaml, build_runtime_from_env
from yom.tools import Tool, ToolResult, tool, ToolRegistry, CORE_TOOLS
from yom.models import AgentState, Message, RuntimeRunResult
from yom.session import SessionBackend, FileSessionBackend, InMemorySessionBackend
from yom.hooks import HookRegistry, HookResult, block, allow, global_hooks, HOOK_NAMES
from yom.skills import Skill, LoadedSkills, load_skills, format_skills_for_prompt
from yom.context import (
    ContextConfig,
    ContextManager,
    ContextStats,
    TruncationStrategy,
    TokenCounter,
    create_token_counter,
    estimate_tokens,
)
from yom.providers import (
    LLMResponse,
    CompletionConfig,
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
    OllamaProvider,
    LMStudioProvider,
    create_local_provider,
)
from yom.plugins import (
    Plugin,
    ToolPlugin,
    ProviderPlugin,
    MiddlewarePlugin,
    PluginManager,
    PluginDiscovery,
    HotReloader,
    ToolVersionRegistry,
    Container,
    YomApp,
)
from yom.debug import (
    DEBUG,
    TRACE,
    enable_debug,
    enable_trace,
    disable_debug,
    trace,
    debug,
    get_recorder,
    inspect_state,
    format_trace_html,
)
from yom.testing import (
    MockProvider,
    fake_agent,
    assert_response,
    assert_tool_calls,
    run_test_suite,
)
from yom.toolsets import (
    http_request,
    get_json,
    query_db,
    db_schema,
    github_api,
    github_read_file,
    github_search,
    s3_put,
    s3_get,
    s3_list,
    shell,
    shell_script,
)

__version__ = "0.1.1"

__all__ = [
    # Version
    "__version__",
    # Core Agent
    "Agent",
    "AgentRuntime",
    "CoreRuntime",
    "DEFAULT_SYSTEM_PROMPT",
    # Configuration
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
    # Built-in Toolsets
    "http_request",
    "get_json",
    "query_db",
    "db_schema",
    "github_api",
    "github_read_file",
    "github_search",
    "s3_put",
    "s3_get",
    "s3_list",
    "shell",
    "shell_script",
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
    # Context
    "ContextConfig",
    "ContextManager",
    "ContextStats",
    "TruncationStrategy",
    "TokenCounter",
    "create_token_counter",
    "estimate_tokens",
    # Providers
    "LLMResponse",
    "CompletionConfig",
    "Message",
    "StreamChunk",
    "Usage",
    "BaseProvider",
    "ProviderFactory",
    "create_provider",
    "create_local_provider",
    "infer_provider",
    "get_api_key",
    "AnthropicProvider",
    "OpenAIProvider",
    "GoogleProvider",
    "OllamaProvider",
    "LMStudioProvider",
    # Plugin System
    "Plugin",
    "ToolPlugin",
    "ProviderPlugin",
    "MiddlewarePlugin",
    "PluginManager",
    "PluginDiscovery",
    "HotReloader",
    "ToolVersionRegistry",
    "Container",
    "YomApp",
    # Debug
    "DEBUG",
    "TRACE",
    "enable_debug",
    "enable_trace",
    "disable_debug",
    "trace",
    "debug",
    "get_recorder",
    "inspect_state",
    "format_trace_html",
    # Testing
    "MockProvider",
    "fake_agent",
    "assert_response",
    "assert_tool_calls",
    "run_test_suite",
]

try:
    from yom.fastapi import AgentRouter, create_agent_router, create_agent_app
    __all__.extend(["AgentRouter", "create_agent_router", "create_agent_app"])
except ImportError:
    pass
