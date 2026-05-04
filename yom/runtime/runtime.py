"""AgentRuntime - main orchestrator for agent execution."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import TYPE_CHECKING, Any, Callable

from yom.models import AgentState, RuntimeRunResult
from yom.runtime.config import RuntimeSettings
from yom.runtime.deps import RuntimeDeps
from yom.tools.result import ToolResult
from yom.providers import create_provider, CompletionConfig

if TYPE_CHECKING:
    from yom.tools import Tool

DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant. Respond to the user's requests concisely and accurately."
DEFAULT_MODEL = "MiniMax-M2.7"


def _get_tool_name(tool: Any) -> str:
    return getattr(tool, "_tool_name", None) or getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")


def _get_tool_execute(tool: Any) -> Callable:
    if hasattr(tool, "execute"):
        return tool.execute
    return tool


def _get_tool_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "_tool_parameters", None) or getattr(tool, "parameters", {}) or {}
    name = _get_tool_name(tool)
    if "name" not in schema:
        schema = {"name": name, "parameters": schema}

    parameters = schema.get("parameters", schema)
    return {
        "name": name,
        "description": getattr(tool, "_tool_description", "") or "",
        "input_schema": parameters,
    }


class AgentRuntime:
    """
    Main orchestrator for agent execution.

    Owns dependency graph, creates/loads agent state, runs agent loop,
    and coordinates sessions/events/hooks/sub-agents.
    """

    def __init__(
        self,
        deps: RuntimeDeps | None,
        settings: RuntimeSettings,
    ):
        self._deps = deps or RuntimeDeps()
        self._settings = settings
        self._tools: list[Tool | Callable] = list(settings.tools)

    @property
    def settings(self) -> RuntimeSettings:
        return self._settings

    @property
    def tools(self) -> list[Tool | Callable]:
        return self._tools

    def list_tools(self) -> list[Tool | Callable]:
        """List all available tools."""
        return self._tools

    def get_tool(self, name: str) -> Tool | Callable | None:
        """Get a tool by name."""
        for tool in self._tools:
            if _get_tool_name(tool) == name:
                return tool
        return None

    async def call_tool(self, name: str, input_data: dict[str, Any]) -> str:
        """
        Call a tool by name with input data.

        Returns the tool result as a string.
        """
        tool = self.get_tool(name)
        if tool is None:
            return f"unknown_tool: {name}"

        execute_fn = _get_tool_execute(tool)
        try:
            result = execute_fn(**input_data)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, ToolResult):
                return result.content
            return str(result)
        except Exception as e:
            return f"tool_error: {e}"

    def create_state(self, session_id: str | None = None) -> AgentState:
        """Create a new agent state."""
        system_prompt = self._settings.get_system_prompt()
        if not system_prompt:
            system_prompt = DEFAULT_SYSTEM_PROMPT
        return AgentState.create(
            runtime_id=self._settings.runtime_id,
            session_id=session_id,
            max_turns=self._settings.max_turns,
            system_prompt=system_prompt,
        )

    async def run_turn(self, state: AgentState) -> str:
        """
        Run a single turn of the agent loop.

        Returns the assistant's response text.
        """
        raise NotImplementedError("Subclass must implement run_turn")

    async def run_prompt(
        self,
        *,
        prompt: str,
        session_id: str | None = None,
    ) -> RuntimeRunResult:
        """
        Run a complete prompt through the agent.

        Creates a new session or resumes existing one.
        """
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

    async def shutdown(self) -> None:
        """Clean up runtime resources."""
        pass


class StandaloneRuntime(AgentRuntime):
    """
    Standalone AgentRuntime with real LLM calls and tool calling.

    Uses yom's provider system for LLM calls.
    Does not depend on coding_agent.
    """

    def __init__(
        self,
        deps: RuntimeDeps | None,
        settings: RuntimeSettings,
    ):
        super().__init__(deps, settings)
        self._provider = None
        self._hooks = deps.hooks if deps else None

    @property
    def hooks(self):
        """Get the hooks registry."""
        return self._hooks

    def _get_provider(self):
        """Get or create LLM provider."""
        if self._provider is None:
            self._provider = create_provider(
                model=self._settings.default_model,
                provider=self._settings.provider,
                api_key=self._settings.api_key,
                base_url=self._settings.base_url,
            )
        return self._provider

    def _get_completion_config(self) -> CompletionConfig:
        """Get completion config from settings."""
        model_config = None
        if self._settings.default_model and self._settings.model_configs:
            model_config = self._settings.model_configs.get(self._settings.default_model)

        if model_config:
            return CompletionConfig(
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens or 4096,
                top_p=model_config.top_p,
                stop_sequences=model_config.stop_sequences,
            )
        return CompletionConfig(temperature=0.7, max_tokens=4096)

    async def run_turn(self, state: AgentState) -> str:
        """Run a turn using the agent loop with LLM and tool calling."""
        if not state.messages:
            return "No messages to process"

        iteration = state.current_turn

        if self._hooks:
            await self._hooks.emit("before_turn", state=state, iteration=iteration)

        provider = self._get_provider()
        model = self._settings.default_model or DEFAULT_MODEL
        config = self._get_completion_config()

        # Import here to avoid circular
        from yom.loop import AgentLoop

        loop = AgentLoop(provider=provider, tools=self._tools)
        config_obj = loop.config
        config_obj.max_turns = self._settings.max_turns

        try:
            response_content, tool_calls, tool_count = await loop.run_turn(
                messages=state.messages,
                model=model,
                config=config,
            )
        except Exception as e:
            if self._hooks:
                await self._hooks.emit("on_error", state=state, error=str(e))
            response_content = f"Error: {e}"

        from yom.models.messages import AssistantMessage
        state.add_message(AssistantMessage(content=response_content))
        state.current_turn += 1

        if self._hooks:
            await self._hooks.emit("after_turn", state=state, iteration=iteration, response=response_content)

        return response_content


def create_standalone_runtime(settings: RuntimeSettings) -> StandaloneRuntime:
    """Create a standalone runtime for simple use cases."""
    return StandaloneRuntime(deps=None, settings=settings)