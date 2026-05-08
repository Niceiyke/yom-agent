#!/usr/bin/env python3
"""Real-world demonstration of P0-P3 features.

Run: python examples/demo_new_features.py
"""

import asyncio
import tempfile
from pathlib import Path

# =============================================================================
# P0: STATE ACCESS + CANCELLATION DEMOS
# =============================================================================

async def demo_state_access():
    """Demonstrate state access after operations."""
    print("\n" + "="*60)
    print("P0: State Access")
    print("="*60)
    
    from yom import Agent, AgentState
    
    agent = Agent(tools=["core"])
    
    # Simulate state
    state = AgentState.create(runtime_id="demo", session_id="session-123")
    state.add_user_message("Hello!")
    state.add_assistant_message("Hi there! How can I help?")
    agent._state = state
    
    # Access state
    print(f"Session ID: {agent.state.session_id}")
    print(f"Runtime ID: {agent.state.runtime_id}")
    print(f"Turn Count: {agent.state.current_turn}")
    print(f"Message Count: {len(agent.state.messages)}")
    print(f"Messages: {[m.content for m in agent.state.messages]}")
    print(f"Provider: {agent.llm_provider}")


async def demo_cancellation():
    """Demonstrate cancellation with timeout."""
    print("\n" + "="*60)
    print("P0: Cancellation Token")
    print("="*60)
    
    from yom.cancellation import CancellationToken
    
    token = CancellationToken()
    
    # Simulate a task that checks cancellation
    async def long_task(token):
        print("Starting long task...")
        for i in range(10):
            await asyncio.sleep(0.5)
            print(f"  Step {i+1}/10")
            if token.is_cancelled:
                print(f"  Cancelled! Reason: {token.cancel_reason}")
                return "cancelled"
        return "completed"
    
    # Run with cancellation after 1.5 seconds
    asyncio.create_task(token.cancel_after(1.5))
    result = await long_task(token)
    print(f"Task result: {result}")


async def demo_agent_abort():
    """Demonstrate Agent.abort()."""
    print("\n" + "="*60)
    print("P0: Agent.abort()")
    print("="*60)
    
    from yom import Agent
    
    agent = Agent(tools=["core"])
    
    print(f"Agent is running: {agent.is_running}")
    print("Calling agent.abort()...")
    agent.abort("User requested abort")
    print(f"Abort token cancelled: {agent._abort_token.is_cancelled}")
    print(f"Abort reason: {agent._abort_token.cancel_reason}")


# =============================================================================
# P1: TOOL FACTORY + EVENTS DEMOS
# =============================================================================

async def demo_tool_factory():
    """Demonstrate tool factories with custom cwd."""
    print("\n" + "="*60)
    print("P1: Tool Factory with Custom CWD")
    print("="*60)
    
    from yom.tools import create_core_tools
    
    with tempfile.TemporaryDirectory() as project_dir:
        # Create a project structure
        src_dir = Path(project_dir) / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("print('Hello, World!')")
        (src_dir / "config.py").write_text("DEBUG = True")
        
        # Create tools bound to this project
        tools = create_core_tools(
            cwd=project_dir,
            allowed_commands=["cat", "ls", "python"]
        )
        
        print(f"Created {len(tools)} tools bound to: {project_dir}")
        print(f"Tool names: {[getattr(t, '_tool_name', 'unknown') for t in tools]}")
        
        # Use the read tool
        from yom.tools import create_read_tool
        read = create_read_tool(cwd=project_dir)
        result = read("src/app.py")
        content = result.content if hasattr(result, 'content') else str(result)
        print("\nReading 'src/app.py' relative to cwd:")
        print(f"  Content: {content[:50]}...")


async def demo_event_subscription():
    """Demonstrate event subscription."""
    print("\n" + "="*60)
    print("P1: Event Subscription")
    print("="*60)
    
    from yom import Agent
    
    agent = Agent(tools=["core"])
    
    # Track events
    events = []
    
    def on_event(event):
        events.append(event.type)
        print(f"  Event received: {event.type.name}")
    
    # Subscribe
    unsubscribe = agent.subscribe(on_event)
    
    # Emit some events
    print("Emitting events...")
    agent._emit_turn_start(1)
    agent._emit_message_delta("Hello")
    agent._emit_tool_start("read", {"path": "/tmp/test.txt"})
    agent._emit_tool_end("read", "file content here")
    agent._emit_turn_end(1, "Here's what I found")
    
    # Unsubscribe
    unsubscribe()
    
    print(f"\nTotal events received: {len(events)}")
    print(f"Event types: {[e.name for e in events]}")


# =============================================================================
# P2: DEFINE_TOOL + CLEANUP DEMOS
# =============================================================================

async def demo_define_tool():
    """Demonstrate define_tool function."""
    print("\n" + "="*60)
    print("P2: define_tool() Function")
    print("="*60)
    
    from yom.tools import define_tool
    
    # Define a weather tool
    def get_weather(location: str) -> str:
        return f"The weather in {location} is sunny, 72°F"
    
    weather_tool = define_tool(
        name="get_weather",
        description="Get current weather for a location",
        schema={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
        }
    )(get_weather)
    
    print(f"Created tool: {weather_tool._tool_name}")
    print(f"Description: {weather_tool._tool_description}")
    
    # Use it
    result = weather_tool(location="San Francisco")
    content = result.content if hasattr(result, 'content') else str(result)
    print(f"Result: {content}")


async def demo_pydantic_schema():
    """Demonstrate Pydantic schema conversion."""
    print("\n" + "="*60)
    print("P2: Pydantic Schema Conversion")
    print("="*60)
    
    try:
        from pydantic import BaseModel, Field

        from yom.tools import pydantic_to_schema
        
        class DeployInput(BaseModel):
            environment: str = Field(description="Target environment (prod/staging/dev)")
            version: str = Field(description="Version to deploy")
            dry_run: bool = Field(default=False, description="If True, simulate only")
        
        schema = pydantic_to_schema(DeployInput)
        print("Pydantic model converted to JSON Schema:")
        print(f"  Type: {schema['type']}")
        print(f"  Properties: {list(schema['properties'].keys())}")
        print(f"  Required: {schema.get('required', [])}")
        
    except ImportError:
        print("Pydantic not installed - skipping")


async def demo_async_context_manager():
    """Demonstrate async context manager."""
    print("\n" + "="*60)
    print("P2: Async Context Manager")
    print("="*60)
    
    from yom import Agent
    
    async with Agent(tools=["core"]) as agent:
        print("Agent initialized inside async context")
        print(f"Runtime created: {agent._runtime is not None}")
    
    print("Agent disposed on context exit")


# =============================================================================
# P3: HOOK REGISTRY + RPC DEMOS
# =============================================================================

async def demo_hook_registry():
    """Demonstrate enhanced HookRegistry."""
    print("\n" + "="*60)
    print("P3: Hook Registry Enhancements")
    print("="*60)
    
    from yom.hooks import HookRegistry
    
    hooks = HookRegistry()
    
    async def hook1(state): print("  hook1 called")
    async def hook2(state): print("  hook2 called")
    
    # Register hooks
    hooks.register("agent_start", hook1)
    hooks.before("agent_start", hook2)
    hooks.after("agent_start", lambda state: print("  after hook"))
    
    print(f"Total hooks for 'agent_start': {hooks.count('agent_start')}")
    print(f"Has hook1: {hooks.has_hook('agent_start', hook1)}")
    
    # Get hooks by category
    categorized = hooks.get_hooks("agent_start")
    print(f"Before hooks: {len(categorized['before'])}")
    print(f"Main hooks: {len(categorized['main'])}")
    print(f"After hooks: {len(categorized['after'])}")
    
    # Unregister
    hooks.unregister("agent_start", hook1)
    print(f"After unregister: {hooks.count('agent_start')}")
    
    # List all events with hooks
    hooks.register("agent_end", lambda state: None)
    events_with_hooks = hooks.list_events()
    print(f"Events with hooks: {events_with_hooks}")


def demo_rpc_protocol():
    """Demonstrate RPC protocol."""
    print("\n" + "="*60)
    print("P3: RPC Protocol")
    print("="*60)
    
    from yom.rpc import ErrorCode, JSONRPCRequest, JSONRPCResponse, error_response
    
    # Create request
    req = JSONRPCRequest(
        id=1,
        method="agent.run",
        params={"prompt": "Hello, world!"}
    )
    print(f"Request: {req.to_dict()}")
    
    # Create response
    resp = JSONRPCResponse(id=1, result={"content": "Hello back!"})
    print(f"Response: {resp.to_dict()}")
    
    # Create error
    err = error_response(2, ErrorCode.METHOD_NOT_FOUND, "Unknown method")
    print(f"Error: {err.to_dict()}")


# =============================================================================
# INTEGRATION DEMO
# =============================================================================

async def demo_integration():
    """Full integration demo."""
    print("\n" + "="*60)
    print("INTEGRATION: Complete Agent Workflow")
    print("="*60)
    
    from yom import Agent
    from yom.cancellation import CancellationToken
    from yom.events import AgentEventType
    from yom.tools import create_core_tools, define_tool
    
    # Create agent with custom tools
    def get_status() -> str:
        import psutil
        return f"CPU: {psutil.cpu_percent()}%, Memory: {psutil.virtual_memory().percent}%"
    
    status_tool = define_tool(
        name="get_status",
        description="Get system status",
        schema={"type": "object", "properties": {}}
    )(get_status)
    
    tools = create_core_tools(cwd="/tmp")
    tools.append(status_tool)
    
    agent = Agent(tools=tools, system_prompt="You are a helpful system assistant.")
    
    # Subscribe to events
    def track_events(event):
        if event.type == AgentEventType.TOOL_START:
            print(f"  [EVENT] Starting tool: {event.data.get('tool_name')}")
        elif event.type == AgentEventType.TOOL_END:
            result = event.data.get('result', '')[:30]
            print(f"  [EVENT] Tool finished: {result}...")
    
    agent.subscribe(track_events)
    
    # Use cancellation
    _token = CancellationToken()

    print("\nAgent ready with:")
    print(f"  - Tools: {[getattr(t, '_tool_name', str(t)) for t in agent._resolved_tools]}")
    print("  - Event subscription: active")
    print("  - Cancellation token: available")
    
    # Emit a turn
    agent._emit_turn_start(1)
    agent._emit_message_delta("I'll check the status for you...")
    agent._emit_turn_end(1, "Here's the system status.")
    
    print("\nIntegration demo complete!")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run all demos."""
    print("="*60)
    print("YOM P0-P3 FEATURES DEMONSTRATION")
    print("="*60)
    
    await demo_state_access()
    await demo_cancellation()
    await demo_agent_abort()
    await demo_tool_factory()
    await demo_event_subscription()
    await demo_define_tool()
    await demo_pydantic_schema()
    await demo_async_context_manager()
    await demo_hook_registry()
    demo_rpc_protocol()
    await demo_integration()
    
    print("\n" + "="*60)
    print("ALL DEMOS COMPLETE!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
