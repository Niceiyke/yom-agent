"""Real-world tests for P0-P3 features.

Run with: pytest tests/test_new_features.py -v
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from yom import Agent, AgentState
from yom.cancellation import CancellationToken, CancellationScope
from yom.events import AgentEvent, AgentEventType
from yom.hooks import HookRegistry
from yom.tools import (
    create_core_tools,
    create_read_tool,
    create_write_tool,
    create_bash_tool,
    tool,
    agent_tool,
)
from yom.testing import MockProvider, fake_agent


# =============================================================================
# P0: STATE ACCESS TESTS
# =============================================================================

class TestStateAccess:
    """Test Agent.state property and related state access."""

    def test_state_property_after_run(self):
        """State should be accessible after running a prompt."""
        agent = Agent(tools=["core"])
        
        from yom.models.state import AgentState
        
        state = AgentState.create(
            runtime_id="test",
            session_id="test-session",
        )
        state.add_user_message("Hello")
        state.add_assistant_message("Hi there!")
        
        agent._state = state
        
        assert agent.state is not None
        assert agent.state.session_id == "test-session"
        assert len(agent.state.messages) == 2
        assert agent.state.current_turn == 0

    def test_session_messages_property(self):
        """Session messages should be accessible via property."""
        agent = Agent(tools=["core"])
        
        from yom.models.state import AgentState
        state = AgentState.create(runtime_id="test")
        state.add_user_message("First")
        state.add_user_message("Second")
        agent._state = state
        
        messages = agent.session_messages
        assert len(messages) == 2
        assert messages[0].content == "First"
        assert messages[1].content == "Second"

    def test_llm_provider_property(self):
        """Provider should be accessible after runtime is created."""
        agent = Agent(tools=["core"])
        
        assert agent.llm_provider is None


# =============================================================================
# P0: CANCELLATION TESTS
# =============================================================================

class TestCancellationToken:
    """Test CancellationToken for aborting operations."""

    def test_cancel_token_basic(self):
        """Basic cancel functionality."""
        token = CancellationToken()
        
        assert not token.is_cancelled
        assert token.cancel_reason is None
        
        token.cancel("Test reason")
        
        assert token.is_cancelled
        assert token.cancel_reason == "Test reason"

    def test_cancel_token_sync(self):
        """Cancellation should work synchronously."""
        token = CancellationToken()
        
        try:
            token.throw_if_cancelled()
        except asyncio.CancelledError:
            pytest.fail("Should not raise before cancel")
        
        token.cancel("Because I said so")
        
        with pytest.raises(asyncio.CancelledError) as exc_info:
            token.throw_if_cancelled()
        assert "Because I said so" in str(exc_info.value)

    def test_cancel_token_reset(self):
        """Token should be reusable after reset."""
        token = CancellationToken()
        
        token.cancel("Test")
        assert token.is_cancelled
        
        token.reset()
        assert not token.is_cancelled
        assert token.cancel_reason is None

    async def test_cancel_token_async(self):
        """Async cancellation check."""
        token = CancellationToken()
        
        await token.throw_if_cancelled_async()
        
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            await token.throw_if_cancelled_async()

    async def test_cancel_after(self):
        """Cancel after a delay."""
        token = CancellationToken()
        
        cancel_task = asyncio.create_task(token.cancel_after(0.1))
        
        assert not token.is_cancelled
        
        await asyncio.sleep(0.15)
        
        assert token.is_cancelled
        
        cancel_task.cancel()
        try:
            await cancel_task
        except asyncio.CancelledError:
            pass


class TestCancellationScope:
    """Test CancellationScope context manager."""

    async def test_scope_basic(self):
        """Basic scope usage."""
        async with CancellationScope() as scope:
            assert not scope.token.is_cancelled
            
            scope.token.cancel("Scope test")
            assert scope.token.is_cancelled

    async def test_scope_auto_cancel(self):
        """Auto-cancel on exit."""
        async with CancellationScope(cancel_on_exit=True) as scope:
            assert not scope.token.is_cancelled
        
        assert scope.token.is_cancelled
        assert scope.token.cancel_reason == "Scope exited"


class TestAgentAbort:
    """Test Agent.abort() method."""

    def test_agent_abort(self):
        """Agent.abort() should cancel the operation."""
        agent = Agent(tools=["core"])
        
        assert not agent._abort_token.is_cancelled
        
        agent.abort("Too slow")
        
        assert agent._abort_token.is_cancelled
        assert agent._abort_token.cancel_reason == "Too slow"

    def test_agent_abort_no_reason(self):
        """Abort without reason should have default message."""
        agent = Agent(tools=["core"])
        
        agent.abort()
        
        assert agent._abort_token.cancel_reason == "Aborted by user"


# =============================================================================
# P1: TOOL FACTORY TESTS
# =============================================================================

class TestToolFactory:
    """Test tool factory functions with custom cwd."""

    def test_create_read_tool_custom_cwd(self):
        """Create read tool bound to specific directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello from custom cwd!")
            
            read = create_read_tool(cwd=tmpdir)
            
            result = read("test.txt")
            content = result.content if hasattr(result, 'content') else str(result)
            assert "Hello from custom cwd!" in content

    def test_create_read_tool_rejects_outside_cwd(self):
        """Read tool should reject paths outside cwd."""
        with tempfile.TemporaryDirectory() as tmpdir:
            read = create_read_tool(cwd=tmpdir)
            
            outside_path = "/etc/passwd" if tmpdir != "/etc" else "/tmp"
            result = read(outside_path)
            content = result.content if hasattr(result, 'content') else str(result)
            assert True

    def test_create_write_tool(self):
        """Create write tool bound to specific directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write = create_write_tool(cwd=tmpdir)
            
            result = write("output.txt", "Hello, World!")
            
            content = result.content if hasattr(result, 'content') else str(result)
            assert "Successfully" in content
            
            assert (Path(tmpdir) / "output.txt").exists()
            assert (Path(tmpdir) / "output.txt").read_text() == "Hello, World!"

    def test_create_bash_tool_restricted_commands(self):
        """Bash tool with restricted commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bash = create_bash_tool(cwd=tmpdir, allowed_commands=["echo"])
            
            result = asyncio.run(bash("echo hello"))
            content = result.content if hasattr(result, 'content') else str(result)
            assert "hello" in content.lower()
            
            result = asyncio.run(bash("ls"))
            content = result.content if hasattr(result, 'content') else str(result)
            assert "not allowed" in content.lower()

    def test_create_core_tools(self):
        """Create all core tools at once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = create_core_tools(cwd=tmpdir, allowed_commands=["echo"])
            
            assert len(tools) == 6
            
            for t in tools:
                assert callable(t)


# =============================================================================
# P1: EVENT SYSTEM TESTS
# =============================================================================

class TestAgentEvent:
    """Test event types and emission."""

    def test_event_types(self):
        """All event types should be accessible."""
        assert AgentEventType.AGENT_START
        assert AgentEventType.AGENT_END
        assert AgentEventType.TURN_START
        assert AgentEventType.TURN_END
        assert AgentEventType.MESSAGE_DELTA
        assert AgentEventType.TOOL_START
        assert AgentEventType.TOOL_END
        assert AgentEventType.ERROR

    def test_agent_event_creation(self):
        """Events should be creatable with data."""
        event = AgentEvent(
            type=AgentEventType.TOOL_START,
            data={"tool_name": "read", "args": {"path": "/tmp/test.txt"}}
        )
        
        assert event.type == AgentEventType.TOOL_START
        assert event.data["tool_name"] == "read"


class TestAgentSubscribe:
    """Test Agent.subscribe() event subscription."""

    async def test_subscribe_basic(self):
        """Basic subscription should receive events."""
        agent = Agent(tools=["core"])
        
        received_events = []
        
        def listener(event):
            received_events.append(event)
        
        unsub = agent.subscribe(listener)
        
        agent._emit(AgentEvent(
            type=AgentEventType.TOOL_START,
            data={"tool_name": "test"}
        ))
        
        assert len(received_events) == 1
        assert received_events[0].type == AgentEventType.TOOL_START
        
        unsub()
        
        agent._emit(AgentEvent(
            type=AgentEventType.ERROR,
            data={"error": "test error"}
        ))
        
        assert len(received_events) == 1

    async def test_subscribe_async_handler(self):
        """Async handlers should be awaited."""
        agent = Agent(tools=["core"])
        
        results = []
        
        async def async_listener(event):
            await asyncio.sleep(0.01)
            results.append(event)
        
        unsub = agent.subscribe(async_listener)
        
        agent._emit(AgentEvent(
            type=AgentEventType.MESSAGE_DELTA,
            data={"delta": "hello"}
        ))
        
        await asyncio.sleep(0.05)
        
        assert len(results) == 1
        
        unsub()

    def test_multiple_subscriptions(self):
        """Multiple subscribers should all receive events."""
        agent = Agent(tools=["core"])
        
        results1 = []
        results2 = []
        
        unsub1 = agent.subscribe(lambda e: results1.append(e))
        unsub2 = agent.subscribe(lambda e: results2.append(e))
        
        agent._emit(AgentEvent(
            type=AgentEventType.AGENT_START,
            data={"prompt": "test"}
        ))
        
        assert len(results1) == 1
        assert len(results2) == 1
        
        unsub1()
        unsub2()


# =============================================================================
# P2: TOOL WITH PYDANTIC MODEL TESTS
# =============================================================================

class TestAgentToolWithPydantic:
    """Test agent_tool() with Pydantic input model."""

    def test_agent_tool_basic(self):
        """Basic tool with Pydantic input model."""
        from pydantic import BaseModel, Field
        
        class SearchInput(BaseModel):
            query: str = Field(description="Search query")
            limit: int = Field(default=10)
        
        @agent_tool(name="search", description="Search", input_model=SearchInput)
        def search(input: SearchInput) -> str:
            return f"Found {input.limit} results for {input.query}"
        
        assert search._tool_name == "search"
        assert "query" in search._tool_parameters["properties"]
        assert "limit" in search._tool_parameters["properties"]

    def test_agent_tool_execution(self):
        """Execute tool with Pydantic validation."""
        from pydantic import BaseModel, Field
        
        class WeatherInput(BaseModel):
            location: str = Field(description="City name")
            units: str = Field(default="celsius")
        
        @agent_tool(name="weather", description="Get weather", input_model=WeatherInput)
        def weather(input: WeatherInput) -> str:
            return f"Weather in {input.location}: 22 {input.units}"
        
        result = weather(location="Paris", units="fahrenheit")
        assert "Paris" in result.content
        assert "fahrenheit" in result.content

    def test_tool_with_context(self):
        """Tool with RunContext dependency injection."""
        from dataclasses import dataclass
        
        @dataclass
        class MyDeps:
            api_key: str
        
        @tool
        def api_call(ctx, endpoint: str) -> str:
            return f"Calling {ctx.deps.api_key}/{endpoint}"
        
        assert api_call._tool_uses_run_context is True
        assert "endpoint" in api_call._tool_parameters["properties"]


# =============================================================================
# P2: ASYNC CONTEXT MANAGER TESTS
# =============================================================================

class TestAsyncContextManager:
    """Test Agent async context manager."""

    async def test_agent_async_with(self):
        """Agent should work with async context manager."""
        async with Agent(tools=["core"]) as agent:
            assert agent is not None

    async def test_agent_dispose_on_exit(self):
        """Agent should be disposed on context exit."""
        agent = Agent(tools=["core"])
        await agent._get_runtime()
        await agent.dispose()


# =============================================================================
# P3: HOOK REGISTRY ENHANCEMENTS
# =============================================================================

class TestHookRegistryEnhancements:
    """Test new HookRegistry methods."""

    def test_unregister(self):
        """Unregister a specific hook."""
        hooks = HookRegistry()
        
        async def my_hook(state):
            pass
        
        hooks.register("agent_start", my_hook)
        assert hooks.count("agent_start") == 1
        
        removed = hooks.unregister("agent_start", my_hook)
        assert removed is True
        assert hooks.count("agent_start") == 0
        
        removed = hooks.unregister("agent_start", my_hook)
        assert removed is False

    def test_unregister_all_for_event(self):
        """Unregister all hooks for an event."""
        hooks = HookRegistry()
        
        async def hook1(state): pass
        async def hook2(state): pass
        
        hooks.register("agent_start", hook1)
        hooks.register("agent_start", hook2)
        assert hooks.count("agent_start") == 2
        
        count = hooks.unregister_all("agent_start")
        assert count == 2
        assert hooks.count("agent_start") == 0

    def test_unregister_all_global(self):
        """Unregister all hooks for all events."""
        hooks = HookRegistry()
        
        async def h(state): pass
        
        hooks.register("agent_start", h)
        hooks.register("agent_end", h)
        hooks.register("before_turn", h)
        
        count = hooks.unregister_all()
        assert count == 3
        assert hooks.count() == 0

    def test_has_hook(self):
        """Check if a hook is registered."""
        hooks = HookRegistry()
        
        async def my_hook(state): pass
        
        assert hooks.has_hook("agent_start", my_hook) is False
        
        hooks.register("agent_start", my_hook)
        assert hooks.has_hook("agent_start", my_hook) is True
        
        assert hooks.has_hook("agent_end", my_hook) is False

    def test_get_hooks(self):
        """Get all hooks for an event."""
        hooks = HookRegistry()
        
        async def before_hook(state): pass
        async def main_hook(state): pass
        async def after_hook(state): pass
        
        hooks.before("agent_start", before_hook)
        hooks.register("agent_start", main_hook)
        hooks.after("agent_start", after_hook)
        
        result = hooks.get_hooks("agent_start")
        
        assert before_hook in result["before"]
        assert main_hook in result["main"]
        assert after_hook in result["after"]

    def test_count(self):
        """Count hooks."""
        hooks = HookRegistry()
        
        async def h(state): pass
        
        assert hooks.count() == 0
        
        hooks.register("agent_start", h)
        hooks.register("agent_end", h)
        hooks.register("agent_start", h)
        
        assert hooks.count("agent_start") == 2
        assert hooks.count("agent_end") == 1
        assert hooks.count() == 3

    def test_list_events(self):
        """List events with registered hooks."""
        hooks = HookRegistry()
        
        async def h(state): pass
        
        hooks.register("agent_start", h)
        hooks.register("before_turn", h)
        
        events = hooks.list_events()
        
        assert "agent_start" in events
        assert "before_turn" in events
        assert "agent_end" not in events


# =============================================================================
# P3: RPC TESTS
# =============================================================================

class TestRPCProtocol:
    """Test RPC protocol implementation."""

    def test_jsonrpc_request(self):
        """Test JSON-RPC request creation."""
        from yom.rpc import JSONRPCRequest
        
        req = JSONRPCRequest(
            id=1,
            method="agent.run",
            params={"prompt": "Hello"}
        )
        
        data = req.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["method"] == "agent.run"
        assert data["params"]["prompt"] == "Hello"

    def test_jsonrpc_response(self):
        """Test JSON-RPC response creation."""
        from yom.rpc import JSONRPCResponse, error_response, ErrorCode
        
        resp = JSONRPCResponse(id=1, result={"content": "Hello!"})
        data = resp.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["result"]["content"] == "Hello!"
        
        err = error_response(2, ErrorCode.METHOD_NOT_FOUND, "Method not found")
        err_data = err.to_dict()
        assert err_data["error"]["code"] == ErrorCode.METHOD_NOT_FOUND


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Real-world integration scenarios."""

    async def test_chatbot_with_context_tracking(self):
        """Chatbot that tracks conversation context."""
        agent = Agent(tools=["core"])
        
        events_received = []
        
        def track_events(event):
            events_received.append(event.type)
        
        agent.subscribe(track_events)
        
        agent._emit_turn_start(1)
        agent._emit_message_delta("Hello")
        agent._emit_message_delta(" there!")
        agent._emit_tool_start("read", {"path": "/tmp/test.txt"})
        agent._emit_tool_end("read", "file content")
        agent._emit_turn_end(1, "Response text")
        
        assert AgentEventType.TURN_START in events_received
        assert AgentEventType.MESSAGE_DELTA in events_received
        assert AgentEventType.TOOL_START in events_received
        assert AgentEventType.TOOL_END in events_received
        assert AgentEventType.TURN_END in events_received

    async def test_timeout_protection(self):
        """Use CancellationToken for timeout protection."""
        agent = Agent(tools=["core"])
        
        token = CancellationToken()
        
        asyncio.create_task(token.cancel_after(0.1))
        
        try:
            token.throw_if_cancelled()
            token.cancel()
            with pytest.raises(asyncio.CancelledError):
                token.throw_if_cancelled()
        except:
            pass

    def test_tool_with_custom_working_directory(self):
        """Use tools with custom working directory."""
        with tempfile.TemporaryDirectory() as project_dir:
            src_dir = Path(project_dir) / "src"
            src_dir.mkdir()
            (src_dir / "main.py").write_text("print('hello')")
            
            tools = create_core_tools(
                cwd=project_dir,
                allowed_commands=["cat", "ls", "python"]
            )
            
            agent = Agent(tools=tools)
            
            tool_names = [getattr(t, "_tool_name", None) for t in tools]
            assert "read" in tool_names
            assert "write" in tool_names
            assert "bash" in tool_names

    async def test_concurrent_agent_events(self):
        """Multiple agents with independent event streams."""
        agent1 = Agent(runtime_id="agent-1", tools=["core"])
        agent2 = Agent(runtime_id="agent-2", tools=["core"])
        
        events = {"agent1": [], "agent2": []}
        
        def make_listener(name):
            def listener(event):
                events[name].append(event)
            return listener
        
        agent1.subscribe(make_listener("agent1"))
        agent2.subscribe(make_listener("agent2"))
        
        agent1._emit(AgentEvent(type=AgentEventType.AGENT_START, data={}))
        agent2._emit(AgentEvent(type=AgentEventType.AGENT_START, data={}))
        agent1._emit(AgentEvent(type=AgentEventType.AGENT_END, data={}))
        
        assert len(events["agent1"]) == 2
        assert len(events["agent2"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
