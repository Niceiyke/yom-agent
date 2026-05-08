"""Simple Agent API for building AI agents."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from yom.cancellation import CancellationToken, _register_abort_token, _unregister_abort_token
from yom.config import RuntimeSettings
from yom.events import AgentEvent, AgentEventType
from yom.factories import build_runtime
from yom.session import FileSessionBackend, InMemorySessionBackend
from yom.subagent import (
    SubAgentDefinition,
    SubAgentManager,
    create_catalog_tool,
    create_spawn_tool,
)
from yom.tools import CORE_TOOLS

if TYPE_CHECKING:
    from yom.models.messages import Message as YomModelMessage
    from yom.models.state import AgentState
    from yom.providers.base import BaseProvider

Tool = Callable

DEFAULT_SESSION_DIR = ".yom/sessions"
DEFAULT_AGENTS_DIR = ".yom/agents"

EventListener = Callable[[AgentEvent], None | asyncio.Task[None]]


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

    With event subscription:
        agent = Agent(tools=["core"])
        unsub = agent.subscribe(lambda e: print(f"Event: {e.type.name}"))
        await agent.run("Hello")
        unsub()

    With cancellation:
        token = CancellationToken()
        asyncio.create_task(token.cancel_after(30))  # Cancel after 30s
        await agent.run("Slow task...", cancellation_token=token)

    As async context manager:
        async with Agent(tools=["core"]) as agent:
            await agent.run("Hello")
        # Auto-cleanup on exit
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
    agents_dir: Path | str | None = None
    enable_spawn: bool = True
    max_subagent_depth: int = 4

    def __post_init__(self):
        self._session = None
        self._runtime = None
        self._subagent_manager = None
        self._state = None  # Current agent state
        self._cancel_token: CancellationToken | None = None
        self._abort_token = CancellationToken()
        self._is_running = False
        
        # Event system
        self._listeners: list[EventListener] = []
        self._listener_id = 0
        
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
        
        # Register abort token
        _register_abort_token(id(self), self._abort_token)
        
        return self._runtime

    # =========================================================================
    # State Property - P0
    # =========================================================================
    
    @property
    def state(self) -> "AgentState | None":
        """Get the current agent state.
        
        Returns:
            The current AgentState if a session is active, None otherwise.
        
        Example:
            agent = Agent(tools=["core"])
            await agent.run("Hello")
            print(agent.state.messages)  # Access messages
            print(agent.state.current_turn)  # Access turn count
        """
        return self._state
    
    @property
    def session_messages(self) -> list["YomModelMessage"]:
        """Get messages from current session.
        
        Returns:
            List of messages in the current session.
        """
        if self._state:
            return self._state.messages
        return []

    # =========================================================================
    # Provider Access - P0
    # =========================================================================
    
    @property
    def llm_provider(self) -> "BaseProvider | None":
        """Get the underlying LLM provider.
        
        Returns:
            The BaseProvider instance if runtime is initialized.
        """
        if self._runtime:
            return self._runtime._get_provider()
        return None

    # =========================================================================
    # Event System - P1
    # =========================================================================
    
    def subscribe(self, listener: EventListener) -> Callable[[], None]:
        """Subscribe to agent events.
        
        Args:
            listener: Callable that receives AgentEvent objects.
                      If it returns an asyncio.Task, it's awaited after the event.
                      Return None for fire-and-forget.
        
        Returns:
            Unsubscribe function.
        
        Example:
            def handle_event(event):
                print(f"Event: {event.type.name}")
            
            # Subscribe
            unsub = agent.subscribe(handle_event)
            
            # Unsubscribe when done
            unsub()
            
            # With async handler
            async def async_handler(event):
                await save_event(event)
            
            unsub = agent.subscribe(async_handler)
        """
        listener_id = self._listener_id
        self._listener_id += 1
        
        entry = (listener_id, listener)
        self._listeners.append(entry)
        
        def unsubscribe():
            for i, (lid, _) in enumerate(self._listeners):
                if lid == listener_id:
                    self._listeners.pop(i)
                    break
        
        return unsubscribe
    
    def _emit(self, event: AgentEvent) -> None:
        """Emit an event to all listeners."""
        for _, listener in self._listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception:
                # Swallow listener exceptions
                pass
    
    def _emit_turn_start(self, iteration: int) -> None:
        """Emit turn start event."""
        self._emit(AgentEvent(
            type=AgentEventType.TURN_START,
            data={"iteration": iteration}
        ))
    
    def _emit_turn_end(self, iteration: int, response: str, tool_results: list[dict] | None = None) -> None:
        """Emit turn end event."""
        self._emit(AgentEvent(
            type=AgentEventType.TURN_END,
            data={
                "iteration": iteration,
                "response": response,
                "tool_results": tool_results or []
            }
        ))
    
    def _emit_message_delta(self, delta: str) -> None:
        """Emit message delta event."""
        self._emit(AgentEvent(
            type=AgentEventType.MESSAGE_DELTA,
            data={"delta": delta}
        ))
    
    def _emit_tool_start(self, tool_name: str, args: dict) -> None:
        """Emit tool start event."""
        self._emit(AgentEvent(
            type=AgentEventType.TOOL_START,
            data={"tool_name": tool_name, "args": args}
        ))
    
    def _emit_tool_end(self, tool_name: str, result: str, error: str | None = None) -> None:
        """Emit tool end event."""
        self._emit(AgentEvent(
            type=AgentEventType.TOOL_END,
            data={
                "tool_name": tool_name,
                "result": result,
                "error": error
            }
        ))
    
    def _emit_error(self, error: str) -> None:
        """Emit error event."""
        self._emit(AgentEvent(
            type=AgentEventType.ERROR,
            data={"error": error}
        ))

    # =========================================================================
    # Cancellation - P0
    # =========================================================================
    
    def abort(self, reason: str | None = None) -> None:
        """Abort the current operation.
        
        Args:
            reason: Optional reason for aborting.
        
        Example:
            agent = Agent(tools=["core"])
            task = asyncio.create_task(agent.run("Long task..."))
            await asyncio.sleep(5)
            agent.abort("Taking too long")
            await task
        """
        self._abort_token.cancel(reason or "Aborted by user")
    
    @property
    def is_running(self) -> bool:
        """Check if agent is currently processing a request."""
        return self._is_running

    # =========================================================================
    # Tool Calling - P1/P2
    # =========================================================================
    
    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        """Call a tool directly by name.
        
        Args:
            name: Tool name (e.g., "read", "bash")
            args: Tool arguments as dictionary
        
        Returns:
            Tool result as string.
        
        Example:
            agent = Agent(tools=["core"])
            result = await agent.call_tool("read", {"path": "/tmp/test.txt"})
            print(result)
        """
        runtime = await self._get_runtime()
        return await runtime.call_tool(name, args)
    
    def call_tool_sync(self, name: str, args: dict[str, Any]) -> str:
        """Synchronous version of call_tool.
        
        Args:
            name: Tool name
            args: Tool arguments
        
        Returns:
            Tool result as string.
        """
        return asyncio.run(self.call_tool(name, args))

    # =========================================================================
    # Public API
    # =========================================================================
    
    @property
    def available_tools(self) -> list[str]:
        """List available tool names."""
        return [getattr(t, "_tool_name", None) or getattr(t, "name", None) or str(t) for t in self._resolved_tools]

    def run_sync(self, prompt: str, stream: bool = True, **kwargs) -> str:
        """Run a prompt synchronously with streaming by default."""
        return asyncio.run(self.run(prompt, stream=stream, **kwargs))

    async def run(
        self,
        prompt: str,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> str:
        """Run a prompt through the agent with optional streaming.
        
        Args:
            prompt: User prompt
            stream: If True, stream tokens as they arrive. If False (default),
                   wait for complete response before returning.
            stream_callback: Called with each text chunk when streaming
            tool_callback: Called when a tool is executed (name, args)
            cancellation_token: Optional cancellation token to abort the operation
        
        Returns:
            The agent's response
        """
        self._is_running = True
        self._abort_token.reset()
        
        # Use provided token or fall back to abort token
        cancel_token = cancellation_token or self._abort_token
        
        try:
            # Emit agent start
            self._emit(AgentEvent(
                type=AgentEventType.AGENT_START,
                data={"prompt": prompt}
            ))
            
            if stream:
                result = await self._run_stream(
                    prompt,
                    stream_callback=stream_callback,
                    tool_callback=tool_callback,
                    cancellation_token=cancel_token,
                )
                return result.get("content", "") if result else ""
            else:
                return await self._run_nonstream(
                    prompt,
                    cancellation_token=cancel_token,
                )
        except asyncio.CancelledError:
            self._emit_error("Operation cancelled")
            return "[Cancelled]"
        except Exception as e:
            self._emit_error(str(e))
            raise
        finally:
            self._is_running = False

    async def _run_nonstream(
        self,
        prompt: str,
        cancellation_token: CancellationToken | None = None,
    ) -> str:
        """Non-streaming run."""
        runtime = await self._get_runtime()
        session_id = self.session_id
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
            self.session_id = session_id
        
        # Check cancellation before starting
        if cancellation_token:
            cancellation_token.throw_if_cancelled()
        
        # Load or create state
        state = await runtime._settings.session_backend.load(session_id)
        if state is None:
            from yom.models.state import AgentState
            state = AgentState.create(
                runtime_id=runtime._settings.runtime_id,
                system_prompt=runtime._settings.system_prompt or "",
            )
            await runtime._settings.session_backend.save(session_id, state)
        
        self._state = state

        # Emit turn start
        self._emit_turn_start(state.current_turn)
        
        try:
            runtime.set_cancellation_token(cancellation_token)
            result = await runtime.run_prompt(
                prompt=prompt,
                session_id=session_id,
            )
            
            # Reload state after run
            self._state = await runtime._settings.session_backend.load(session_id)
            
            # Emit turn end
            self._emit_turn_end(state.current_turn, result.final_message)
            
            # Emit agent end
            self._emit(AgentEvent(
                type=AgentEventType.AGENT_END,
                data={"final_message": result.final_message}
            ))
            
            return result.final_message
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._emit_error(str(e))
            raise

    async def _run_stream(
        self,
        prompt: str,
        stream_callback: Callable[[str], None] | None,
        tool_callback: Callable[[str, dict], None] | None,
        cancellation_token: CancellationToken | None = None,
    ) -> dict:
        """Streaming run with callbacks, tool execution, and cancellation."""
        runtime = await self._get_runtime()
        
        session_id = self.session_id
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
            self.session_id = session_id
        
        # Initialize session
        state = await runtime._settings.session_backend.load(session_id)
        if state is None:
            from yom.models.state import AgentState
            state = AgentState.create(
                runtime_id=runtime._settings.runtime_id,
                system_prompt=runtime._settings.system_prompt or "",
            )
            await runtime._settings.session_backend.save(session_id, state)
        
        self._state = state
        
        provider = runtime._get_provider()
        model = runtime._settings.default_model or "MiniMax-M2.7"
        config = runtime._get_completion_config()
        
        from yom.loop import AgentLoop
        from yom.providers.base import Message
        
        loop = AgentLoop(provider=provider, tools=self._resolved_tools)
        
        # Track cancellation
        if cancellation_token:
            loop._cancellation_token = cancellation_token
        
        messages = [Message(role="user", content=prompt)]
        
        try:
            collected_content = []
            collected_tool_calls = []
            tool_results = []
            
            # Emit turn start
            self._emit_turn_start(state.current_turn)
            
            async for chunk in loop.stream_turn(messages, model, config):
                # Check for cancellation
                if cancellation_token and cancellation_token.is_cancelled:
                    raise asyncio.CancelledError(cancellation_token.cancel_reason)
                
                if chunk.content:
                    collected_content.append(chunk.content)
                    self._emit_message_delta(chunk.content)
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
                            except Exception:
                                pass
                        from yom.loop import ToolCall
                        tc_obj = ToolCall(
                            tool_call_id=tc.get('id'),
                            name=func.get('name', ''),
                            arguments=args,
                        )
                        collected_tool_calls.append(tc_obj)
                        self._emit_tool_start(tc_obj.name, tc_obj.arguments)
                        if tool_callback:
                            tool_callback(tc_obj.name, tc_obj.arguments)
                
                if chunk.is_final:
                    break
            
            response_content = "".join(collected_content)
            
            # Execute collected tool calls and continue turn if needed
            if collected_tool_calls:
                from yom.loop import ToolResult as YomToolResult
                
                # Execute all tools concurrently
                async def execute_tool(tc):
                    tool = None
                    for t in self._resolved_tools:
                        name = getattr(t, '_tool_name', None) or getattr(t, 'name', None)
                        if name == tc.name:
                            tool = t
                            break
                    if tool is None:
                        return YomToolResult(name=tc.name, content="", error=f"unknown_tool: {tc.name}")
                    
                    execute_fn = getattr(tool, 'execute', None) or tool
                    try:
                        result = execute_fn(**tc.arguments)
                        if asyncio.iscoroutine(result):
                            result = await result
                        if hasattr(result, 'content'):
                            return YomToolResult(name=tc.name, content=result.content)
                        return YomToolResult(name=tc.name, content=str(result))
                    except Exception as e:
                        return YomToolResult(name=tc.name, content="", error=f"tool_error: {e}")
                
                tool_results = await asyncio.gather(*[execute_tool(tc) for tc in collected_tool_calls])
                
                # Build messages for continued turn
                messages.append(Message(role="assistant", content=response_content))
                for tr, tc in zip(tool_results, collected_tool_calls, strict=False):
                    tc_id = tc.tool_call_id or tc.id or f"call_{id(tc)}"
                    messages.append(Message(
                        role="tool",
                        content=tr.content,
                        tool_call_id=tc_id,
                        name=tc.name,
                    ))
                
                # Continue turn with tool results
                async for chunk in loop.stream_turn(messages, model, config):
                    if cancellation_token and cancellation_token.is_cancelled:
                        raise asyncio.CancelledError(cancellation_token.cancel_reason)
                    
                    if chunk.content:
                        collected_content.append(chunk.content)
                        self._emit_message_delta(chunk.content)
                        if stream_callback:
                            stream_callback(chunk.content)
                    
                    if chunk.is_final:
                        break
                
                response_content = "".join(collected_content)
            
            # Build tool info
            tool_info = []
            for tc in collected_tool_calls:
                tool_info.append({"name": tc.name, "args": tc.arguments})
            
            # Emit turn end
            self._emit_turn_end(state.current_turn, response_content, tool_info)
            
            # Emit agent end
            self._emit(AgentEvent(
                type=AgentEventType.AGENT_END,
                data={"final_message": response_content}
            ))
            
            return {
                "content": response_content,
                "tool_calls": tool_info,
            }
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._emit_error(str(e))
            error_msg = f"Error: {e}"
            return {"content": error_msg, "tool_calls": []}

    def run_stream_sync(
        self,
        prompt: str,
        stream_callback: Callable[[str], None] | None = None,
        tool_callback: Callable[[str, dict], None] | None = None,
    ) -> dict:
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

    # =========================================================================
    # Async Context Manager - P2
    # =========================================================================
    
    async def __aenter__(self) -> "Agent":
        """Enter async context manager."""
        await self._get_runtime()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager - auto cleanup."""
        await self.dispose()
    
    # =========================================================================
    # Resource Cleanup - P2
    # =========================================================================
    
    def clear_session(self) -> None:
        """Clear the current session."""
        self.session_id = None
        self._runtime = None
        self._state = None

    async def dispose(self) -> None:
        """Clean up agent resources.
        
        Removes abort token registration and cleans up runtime.
        Safe to call multiple times.
        
        Example:
            agent = Agent(tools=["core"])
            try:
                await agent.run("Hello")
            finally:
                await agent.dispose()
        """
        _unregister_abort_token(id(self))
        if self._runtime:
            await self._runtime.shutdown()
            self._runtime = None
        self._listeners.clear()
        self._state = None

    async def get_session_messages(self) -> list[dict]:
        """Get all messages in current session."""
        if not self.session_id:
            return []
        runtime = await self._get_runtime()
        state = await runtime._settings.session_backend.load(self.session_id)
        if state:
            return [{"role": m.role.value, "content": m.content} for m in state.messages]
        return []

    # =========================================================================
    # Tool Registration
    # =========================================================================
    
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

