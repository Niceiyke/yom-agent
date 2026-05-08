"""yom: Configurable, installable agent runtime.

Open source agent framework with tool calling, session management,
multi-provider LLM support, and plugin system.
"""

from yom.agent import Agent
from yom.agent_runtime import AgentRuntime, CoreRuntime, DEFAULT_SYSTEM_PROMPT
from yom.config import RuntimeSettings
from yom.deps import RuntimeDeps, SessionManager
from yom.factories import build_runtime, build_runtime_from_yaml, build_runtime_from_env
from yom.tools import Tool, ToolResult, tool, ToolRegistry, CORE_TOOLS, agent_tool, RunContext
from yom.models import (
    AgentState, Message, RuntimeRunResult, TurnResult, 
    UserMessage, AssistantMessage, ToolMessage, SystemMessage, MessageRole,
    AgentOutput, AgentOutputResult, OutputValidationError, validate_output,
)
from yom.session import SessionBackend, FileSessionBackend, InMemorySessionBackend

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
    create_provider,
    OpenAICompatibleProvider,
    AnthropicCompatibleProvider,
    GoogleCompatibleProvider,
)
from yom.plugins import (
    Plugin,
    ToolPlugin,
    YomApp,
)
from yom.debug import (
    DEBUG,
    TRACE,
    enable_debug,
    enable_trace,
    disable_debug,
    trace,
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

# New P0-P3 features
from yom.events import AgentEvent, AgentEventType
from yom.cancellation import CancellationToken, CancellationScope

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
    from yom.fastapi import AgentRouter, create_agent_router, create_agent_app
    __all__.extend(["AgentRouter", "create_agent_router", "create_agent_app"])
except ImportError:
    pass
