"""Simple Agent API for building AI agents."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from yom.config import RuntimeSettings
from yom.factories import build_runtime
from yom.tools import CORE_TOOLS
from yom.session import FileSessionBackend, InMemorySessionBackend
from yom.subagent import (
    SubAgentManager,
    SubAgentDefinition,
    create_spawn_tool,
    create_catalog_tool,
)

Tool = Callable

DEFAULT_SESSION_DIR = ".yom/sessions"
DEFAULT_AGENTS_DIR = ".yom/agents"


@dataclass
class Agent:
    """
    Simple API for building AI agents.

    Example:
        from yom import Agent

        agent = Agent(
            system_prompt="You are helpful",
            tools=["core"]  # includes read, write, edit, bash, cmd
        )

        result = await agent.run("Read /tmp/test.txt")
        print(result)

    With session persistence:
        agent = Agent(session_id="user-123", tools=["core"])
        await agent.run("My name is John")
        # ... later ...
        await agent.run("What is my name?")  # knows "John"

    With sub-agents from markdown files:
        agent = Agent(agents_dir=".yom/agents", tools=["core", "spawn"])
        # Loads .yom/agents/*.md files
        # LLM sees catalog at start, full prompt loaded on spawn
        await agent.run("Review /tmp/code.py")

    Manual sub-agent registration:
        agent = Agent(tools=["core", "spawn"])
        agent.register_subagent(
            name="reviewer",
            description="Reviews code for bugs",
            system_prompt="You are a code reviewer...",
            tools=["core"]
        )
    """

    system_prompt: str = "You are helpful. Use tools when needed."
    tools: list[str | Tool] = field(default_factory=lambda: ["core"])
    runtime_id: str = "agent"
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None

    # Session support
    session_id: str | None = None
    session_backend: str | None = None
    session_dir: Path | str | None = None

    # Sub-agent support
    agents_dir: Path | str | None = None  # Directory containing *.md agent files
    enable_spawn: bool = True
    max_subagent_depth: int = 4

    def __post_init__(self):
        self._session = None
        self._runtime = None
        self._subagent_manager = None

        # Initialize sub-agent manager
        self._init_subagent_manager()

        self._resolved_tools = self._resolve_tools()

    def _init_subagent_manager(self) -> None:
        """Initialize sub-agent manager and load agents from directory if specified."""
        self._subagent_manager = SubAgentManager(max_depth=self.max_subagent_depth)

        if self.agents_dir:
            self._subagent_manager.registry.load_from_directory(self.agents_dir)

    def _resolve_tools(self) -> list[Tool]:
        """Resolve tool specs to actual tools."""
        from yom.toolsets import (
            http_request, get_json,
            query_db, db_schema,
            github_api, github_read_file, github_search,
            s3_put, s3_get, s3_list,
            shell, shell_script,
            telegram_send,
        )
        
        TOOLSET_TOOLS = {
            "http_request": http_request,
            "get_json": get_json,
            "query_db": query_db,
            "db_schema": db_schema,
            "github_api": github_api,
            "github_read_file": github_read_file,
            "github_search": github_search,
            "s3_put": s3_put,
            "s3_get": s3_get,
            "s3_list": s3_list,
            "shell": shell,
            "shell_script": shell_script,
            "telegram_send": telegram_send,
        }
        
        resolved = []
        for tool in self.tools:
            if tool == "core":
                resolved.extend(CORE_TOOLS)
            elif tool == "spawn":
                if self.enable_spawn and self._subagent_manager:
                    spawn_tool = create_spawn_tool(self._subagent_manager)
                    resolved.append(spawn_tool)
                    catalog_tool = create_catalog_tool(self._subagent_manager)
                    resolved.append(catalog_tool)
            elif callable(tool):
                resolved.append(tool)
            elif isinstance(tool, str):
                # Check if it's a toolset tool
                if tool in TOOLSET_TOOLS:
                    resolved.append(TOOLSET_TOOLS[tool])
                else:
                    # Check CORE_TOOLS
                    found = False
                    for t in CORE_TOOLS:
                        name = getattr(t, "_tool_name", None) or getattr(t, "name", None)
                        if name == tool:
                            resolved.append(t)
                            found = True
                            break
                    if not found:
                        raise ValueError(f"Unknown tool: {tool}")
            else:
                raise TypeError(f"Invalid tool type: {type(tool)}")
        return resolved

    def _get_system_prompt_with_catalog(self) -> str:
        """Get system prompt with sub-agent catalog appended."""
        prompt = self.system_prompt
        if self._subagent_manager and self.enable_spawn:
            catalog_text = self._subagent_manager.registry.get_catalog_text()
            if catalog_text != "No sub-agents available.":
                prompt = f"{prompt}\n\n{catalog_text}\n\nWhen you need specialized help, use spawn_agent to call a sub-agent."
        return prompt

    def _get_session_backend(self):
        """Get or create session backend."""
        if self.session_backend == "file":
            if self.session_dir:
                base_dir = Path(self.session_dir) / DEFAULT_SESSION_DIR / self.runtime_id
            else:
                base_dir = Path.cwd() / DEFAULT_SESSION_DIR / self.runtime_id
            return FileSessionBackend(base_dir=base_dir)
        elif self.session_backend == "memory" or self.session_backend is None:
            # Default to memory backend for session persistence
            return InMemorySessionBackend()
        return None

    async def _get_runtime(self):
        """Get or create runtime with session support."""
        if self._runtime is not None:
            return self._runtime

        session_backend = self._get_session_backend()

        settings = RuntimeSettings(
            runtime_id=self.runtime_id,
            system_prompt=self._get_system_prompt_with_catalog(),
            tools=self._resolved_tools,
            default_model=self.model,
            provider=self.provider,
            base_url=self.base_url,
            api_key=self.api_key or os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            session_backend=session_backend,
        )

        self._runtime = build_runtime(settings)
        return self._runtime

    @property
    def available_tools(self) -> list[str]:
        """List available tool names."""
        return [getattr(t, "_tool_name", None) or getattr(t, "name", None) or str(t) for t in self._resolved_tools]

    def run_sync(self, prompt: str, stream: bool = True) -> str:
        """Run a prompt synchronously with streaming by default."""
        return asyncio.run(self.run(prompt, stream=stream))

    async def run(self, prompt: str, stream: bool = True, stream_callback=None, tool_callback=None) -> str:
        """Run a prompt through the agent with optional streaming.
        
        Args:
            prompt: User prompt
            stream: If True, use streaming (default). If False, wait for complete response.
            stream_callback: Called with each text chunk when streaming
            tool_callback: Called when a tool is executed (name, args)
        
        Returns:
            The agent's response
        """
        if stream:
            # Use streaming with callbacks
            result = await self.run_stream(prompt, stream_callback=stream_callback, tool_callback=tool_callback)
            return result.get("content", "") if result else ""
        else:
            # Non-streaming mode - run full turn
            runtime = await self._get_runtime()
            session_id = self.session_id
            if session_id is None:
                import uuid
                session_id = str(uuid.uuid4())
                self.session_id = session_id
            result = await runtime.run_prompt(prompt=prompt, session_id=session_id)
            return result.final_message

    async def run_stream(self, prompt: str, stream_callback=None, tool_callback=None) -> dict:
        """Run a prompt with optional streaming.
        
        Args:
            prompt: The user prompt
            stream_callback: Called with text chunks
            tool_callback: Called when a tool is called
            
        Returns:
            dict with 'content' and 'tool_calls' keys
        """
        runtime = await self._get_runtime()
        
        session_id = self.session_id
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
            self.session_id = session_id
        
        # Initialize session if needed
        if self.session_backend:
            state = await runtime._settings.session_backend.load(session_id)
            if state is None:
                from yom.models.state import AgentState
                state = AgentState.create(
                    runtime_id=runtime._settings.runtime_id,
                    system_prompt=runtime._settings.system_prompt or "",
                )
                await runtime._settings.session_backend.save(session_id, state)
        
        # Add user message
        from yom.models.messages import UserMessage
        if hasattr(runtime, '_state') and runtime._state:
            runtime._state.add_message(UserMessage(content=prompt))
        
        provider = runtime._get_provider()
        model = runtime._settings.default_model or "MiniMax-M2.7"
        config = runtime._get_completion_config()
        
        from yom.loop import AgentLoop
        from yom.providers.base import Message
        
        loop = AgentLoop(provider=provider, tools=self._resolved_tools)
        
        # Run the full turn to get tool calls
        messages = [Message(role="user", content=prompt)]
        
        try:
            # Use stream_turn for true streaming
            collected_content = []
            collected_tool_calls = []
            
            async for chunk in loop.stream_turn(messages, model, config):
                if chunk.content:
                    collected_content.append(chunk.content)
                    if stream_callback:
                        stream_callback(chunk.content)
                if chunk.raw and 'tool_calls' in chunk.raw:
                    for tc in chunk.raw['tool_calls']:
                        func = tc.get('function', tc)
                        args = func.get('arguments', {})
                        if isinstance(args, str):
                            import json
                            try:
                                args = json.loads(args)
                            except:
                                pass
                        from yom.loop import ToolCall
                        tc_obj = ToolCall(
                            tool_call_id=tc.get('id'),
                            name=func.get('name', ''),
                            arguments=args,
                        )
                        collected_tool_calls.append(tc_obj)
                        if tool_callback:
                            tool_callback(tc_obj.name, tc_obj.arguments)
                if chunk.is_final:
                    break
            
            response_content = "".join(collected_content)
            
            # Report tool calls
            tool_info = []
            for tc in collected_tool_calls:
                tool_info.append({"name": tc.name, "args": tc.arguments})
            
            return {
                "content": response_content,
                "tool_calls": tool_info,
            }
        except Exception as e:
            error_msg = f"Error: {e}"
            if stream_callback:
                stream_callback(error_msg)
            return {"content": error_msg, "tool_calls": []}

    def run_stream_sync(self, prompt: str, stream_callback=None, tool_callback=None) -> dict:
        """Synchronous version of run_stream for non-async contexts.
        
        Usage:
            def on_chunk(text):
                print(text, end="")
            def on_tool(name, args):
                print(f"\n[Tool: {name}]")
            
            result = agent.run_stream_sync("prompt", on_chunk, on_tool)
            # result = {'content': '...', 'tool_calls': [...]}
        """
        return asyncio.run(self.run_stream(prompt, stream_callback, tool_callback))

    def clear_session(self) -> None:
        """Clear the current session."""
        self.session_id = None
        self._runtime = None

    async def get_session_messages(self) -> list[dict]:
        """Get all messages in current session."""
        if not self.session_id:
            return []
        runtime = await self._get_runtime()
        state = await runtime._settings.session_backend.load(self.session_id)
        if state:
            return [{"role": m.role.value, "content": m.content} for m in state.messages]
        return []

    def tool(self, name: str | None = None, description: str | None = None):
        """Decorator to add a custom tool."""
        from yom.tools import tool as yom_tool
        return yom_tool(name=name, description=description)

    def add_tool(self, func: Callable) -> Callable:
        """Add a tool function directly."""
        self._resolved_tools.append(func)
        return func

    def register_subagent(
        self,
        name: str,
        description: str = "",
        system_prompt: str = "",
        tools: list[str] | None = None,
        model: str | None = None,
    ) -> None:
        """Register a sub-agent that can be spawned.

        Example:
            agent.register_subagent(
                name="reviewer",
                description="Reviews code for bugs",
                system_prompt="You are a code reviewer. Analyze code...",
                tools=["core"]
            )
        """
        if self._subagent_manager is None:
            self._subagent_manager = SubAgentManager(max_depth=self.max_subagent_depth)

        self._subagent_manager.registry.register(SubAgentDefinition(
            name=name,
            description=description,
            tools=tools,
            model=model,
            prompt=system_prompt,
            path=None,
        ))

    def list_subagents(self) -> list[str]:
        """List available sub-agent types."""
        if self._subagent_manager is None:
            return []
        return self._subagent_manager.registry.list_agents()