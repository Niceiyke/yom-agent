"""Integration layer connecting agent-core to coding_agent internals."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from yom.runtime.config import RuntimeSettings
    from yom.models import AgentState as CoreAgentState


@dataclass
class IntegratedDeps:
    """Runtime dependencies for integrated (yom_agent) mode."""
    tool_registry: Any  # coding_agent.tools.registry.ToolRegistry
    session_manager: Any  # coding_agent.agent.session.SessionManager
    hooks: Any  # coding_agent.hooks.hooks.HookRegistry
    session: Any | None = None  # RuntimeSession
    stream_fn: Callable[..., Any] | None = None


class AgentCoreToolAdapter:
    """
    Adapter that wraps agent-core tools to work with yom_agent's ToolRegistry.

    yom_agent's ToolRegistry expects tools with signature: (input_dict, state) -> str
    This adapter converts agent-core tools to match.
    """

    def __init__(self, tool: Any, tool_schema: dict[str, Any]):
        self._tool = tool
        self._schema = tool_schema

    @property
    def name(self) -> str:
        return self._schema.get("name", getattr(self._tool, "_tool_name", "unknown"))

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": getattr(self._tool, "_tool_description", "") or "",
            "input_schema": self._schema.get("parameters", {}),
        }

    async def execute(self, input_dict: dict[str, Any], state: Any) -> str:
        """Execute the tool and return string result."""
        tool = self._tool
        execute_fn = getattr(tool, "execute", None) or tool

        try:
            result = execute_fn(**input_dict)
            if asyncio.iscoroutine(result):
                result = await result

            from yom.tools.result import ToolResult
            if isinstance(result, ToolResult):
                return result.content
            return str(result)
        except Exception as e:
            return f"tool_error: {e}"


def convert_yom_tools(
    tools: list[Any],
) -> tuple[dict[str, AgentCoreToolAdapter], list[dict[str, Any]]]:
    """
    Convert agent-core tools to yom_agent-compatible format.

    Returns:
        (tool_map, schemas) - tool map for registry and list of schemas
    """
    tool_map = {}
    schemas = []

    for tool in tools:
        name = getattr(tool, "_tool_name", None) or getattr(tool, "name", None)
        if not name:
            continue

        schema = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", {}) or {}
        if "name" not in schema:
            schema = {"name": name, "parameters": schema}

        adapter = AgentCoreToolAdapter(tool, schema)
        tool_map[name] = adapter
        schemas.append(adapter.schema)

    return tool_map, schemas


class YomAgentBridge:
    """
    Bridge that allows agent-core to use yom_agent's agent_loop.

    This is used when you want:
    - Real LLM calls via yom_agent's provider system
    - Access to yom_agent's built-in tools
    - Full session management via yom_agent's SessionManager
    """

    def __init__(
        self,
        deps: IntegratedDeps,
        settings: RuntimeSettings,
    ):
        self._deps = deps
        self._settings = settings

    def convert_state(self, core_state: CoreAgentState) -> Any:
        """Convert agent-core AgentState to yom_agent format."""
        from coding_agent.agent.state import AgentState as CAAgentState

        # Convert messages
        messages = []
        for msg in core_state.messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = msg.content
            msg_dict = {"role": role, "content": content}

            if hasattr(msg, "tool_calls"):
                msg_dict["tool_calls"] = msg.tool_calls
            if hasattr(msg, "tool_name"):
                msg_dict["tool_name"] = msg.tool_name

            messages.append(msg_dict)

        return CAAgentState(
            agent_type=core_state.metadata.get("agent_type", "agent-core"),
            system_prompt=core_state.metadata.get("system_prompt", self._settings.get_system_prompt()),
            model=core_state.metadata.get("model", self._settings.default_model or "MiniMax-M2.7"),
            messages=messages,
            tools=self._get_tool_schemas(),
            depth=core_state.current_turn,
        )

    def _get_tool_schemas(self) -> list[dict]:
        """Get tool schemas in yom_agent format."""
        schemas = []
        for tool in self._settings.tools:
            name = getattr(tool, "_tool_name", None) or getattr(tool, "name", "unknown")
            params = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", {}) or {}
            if not params:
                params = {"type": "object", "properties": {}}
            schemas.append({
                "name": name,
                "description": getattr(tool, "_tool_description", "") or "",
                "input_schema": params,
            })
        return schemas

    async def run_turn(self, core_state: CoreAgentState) -> str:
        """Run a turn using yom_agent's agent_loop."""
        from coding_agent.agent.loop import agent_loop

        ca_state = self.convert_state(core_state)

        result = await agent_loop(
            state=ca_state,
            tool_registry=self._deps.tool_registry,
            hooks=self._deps.hooks,
            session=self._deps.session,
        )

        return result


class YomAgentRuntime:
    """
    AgentRuntime implementation that delegates to yom_agent.

    Use this when you need full yom_agent functionality:
    - Real LLM calls with auth handling
    - Built-in tools (shell, file operations, etc.)
    - Session management
    - Hooks and event system

    Example:
        from yom import RuntimeSettings, build_runtime

        settings = RuntimeSettings(
            runtime_id="my-agent",
            system_prompt="You are helpful",
            tools=[my_tool],
        )
        runtime = build_runtime(settings, mode="yom_agent")
        result = await runtime.run_prompt(prompt="Hello")
    """

    def __init__(
        self,
        deps: IntegratedDeps,
        settings: RuntimeSettings,
    ):
        self._deps = deps
        self._settings = settings
        self._bridge = YomAgentBridge(deps, settings)

    @property
    def settings(self) -> RuntimeSettings:
        return self._settings

    @property
    def list_tools(self) -> list:
        """List tools (from settings)."""
        return self._settings.tools

    def create_state(self, session_id: str | None = None) -> CoreAgentState:
        """Create a new agent-core state."""
        from yom.models import AgentState

        return AgentState.create(
            runtime_id=self._settings.runtime_id,
            session_id=session_id,
            max_turns=self._settings.max_turns,
            system_prompt=self._settings.get_system_prompt(),
        )

    async def run_turn(self, state: CoreAgentState) -> str:
        """Run a turn via yom_agent bridge."""
        return await self._bridge.run_turn(state)

    async def run_prompt(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
    ) -> "RuntimeRunResult":
        """Run a complete prompt."""
        import uuid
        from yom.models import RuntimeRunResult

        session_id = session_id or str(uuid.uuid4())

        # Try to load existing session
        state = None
        if self._settings.session_backend:
            state = await self._settings.session_backend.load(session_id)

        if state is None:
            state = self.create_state(session_id=session_id)

        state.add_user_message(prompt)

        try:
            result = await self.run_turn(state)

            # Save session if backend configured
            if self._settings.session_backend:
                await self._settings.session_backend.save(session_id, state)

            return RuntimeRunResult(
                session_id=session_id,
                runtime_id=self._settings.runtime_id,
                final_message=result,
                turns=state.current_turn,
            )
        except Exception as e:
            return RuntimeRunResult(
                session_id=session_id,
                runtime_id=self._settings.runtime_id,
                final_message="",
                error=str(e),
            )


def create_yom_agent_runtime(
    settings: RuntimeSettings,
    tool_registry: Any | None = None,
    session_manager: Any | None = None,
) -> YomAgentRuntime:
    """
    Create a YomAgentRuntime that uses yom_agent internals.

    Args:
        settings: RuntimeSettings with system_prompt, tools, etc.
        tool_registry: yom_agent ToolRegistry (will create if None)
        session_manager: yom_agent SessionManager (will create if None)
    """
    from coding_agent.tools.registry import ToolRegistry as CAToolRegistry
    from coding_agent.agent.session import SessionManager as CASessionManager, RuntimeSession
    from coding_agent.hooks.hooks import global_hooks

    if tool_registry is None:
        tool_registry = CAToolRegistry()

    if session_manager is None:
        session_manager = CASessionManager()

    # Register agent-core tools into yom_agent registry
    tool_map, schemas = convert_yom_tools(settings.tools)
    for name, adapter in tool_map.items():
        tool_registry.register(adapter.execute, adapter.schema)

    deps = IntegratedDeps(
        tool_registry=tool_registry,
        session_manager=session_manager,
        hooks=global_hooks,
        session=RuntimeSession(),
    )

    return YomAgentRuntime(deps=deps, settings=settings)