"""yom: Configurable, installable agent runtime.

Open source agent framework with tool calling, session management,
multi-provider LLM support, and plugin system.
"""

from yom.agent import Agent
from yom.agent_runtime import DEFAULT_SYSTEM_PROMPT, AgentRuntime, CoreRuntime
from yom.cancellation import CancellationScope, CancellationToken
from yom.config import RuntimeSettings
from yom.context import (
    ContextConfig,
    ContextManager,
    ContextStats,
    TokenCounter,
    TruncationStrategy,
    create_token_counter,
    estimate_tokens,
)
from yom.debug import (
    DEBUG,
    TRACE,
    disable_debug,
    enable_debug,
    enable_trace,
    trace,
)
from yom.deps import RuntimeDeps, SessionManager

# New P0-P3 features
from yom.events import AgentEvent, AgentEventType
from yom.factories import build_runtime, build_runtime_from_env, build_runtime_from_yaml
from yom.models import (
    AgentOutput,
    AgentOutputResult,
    AgentState,
    AssistantMessage,
    Message,
    MessageRole,
    OutputValidationError,
    RuntimeRunResult,
    SystemMessage,
    ToolMessage,
    TurnResult,
    UserMessage,
    validate_output,
)
from yom.plugins import (
    Plugin,
    ToolPlugin,
    YomApp,
)
from yom.providers import (
    AnthropicCompatibleProvider,
    BaseProvider,
    CompletionConfig,
    GoogleCompatibleProvider,
    LLMResponse,
    OpenAICompatibleProvider,
    StreamChunk,
    Usage,
    create_provider,
)
from yom.session import FileSessionBackend, InMemorySessionBackend, SessionBackend
from yom.skills import LoadedSkills, Skill, format_skills_for_prompt, load_skills
from yom.testing import (
    MockProvider,
    assert_response,
    assert_tool_calls,
    fake_agent,
    run_test_suite,
)
from yom.tools import CORE_TOOLS, RunContext, Tool, ToolRegistry, ToolResult, agent_tool, tool
from yom.toolsets import (
    db_schema,
    get_json,
    github_api,
    github_read_file,
    github_search,
    http_request,
    query_db,
    s3_get,
    s3_list,
    s3_put,
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
    "agent_tool",
    "RunContext",
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
    "TurnResult",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "SystemMessage",
    "MessageRole",
    # Output validation
    "AgentOutput",
    "AgentOutputResult",
    "OutputValidationError",
    "validate_output",
    # Session
    "SessionBackend",
    "FileSessionBackend",
    "InMemorySessionBackend",

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
    "StreamChunk",
    "Usage",
    "BaseProvider",
    "create_provider",
    "OpenAICompatibleProvider",
    "AnthropicCompatibleProvider",
    "GoogleCompatibleProvider",
    # Plugin System
    "Plugin",
    "ToolPlugin",
    "YomApp",
    # Debug
    "DEBUG",
    "TRACE",
    "enable_debug",
    "enable_trace",
    "disable_debug",
    "trace",
    # Testing
    "MockProvider",
    "fake_agent",
    "assert_response",
    "assert_tool_calls",
    "run_test_suite",
    # Events & Cancellation
    "AgentEvent",
    "AgentEventType",
    "CancellationToken",
    "CancellationScope",
]

try:
    from yom.fastapi import AgentRouter as AgentRouter  # noqa: F401
    from yom.fastapi import create_agent_app as create_agent_app  # noqa: F401
    from yom.fastapi import create_agent_router as create_agent_router  # noqa: F401

    __all__.extend(["AgentRouter", "create_agent_router", "create_agent_app"])
except ImportError:
    pass
