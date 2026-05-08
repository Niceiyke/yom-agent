#!/usr/bin/env python3
"""Demo of event subscription for monitoring agent execution.

This example demonstrates:
- Using Agent.subscribe() to track events from an agent instance
- Viewing collected event logs after execution

Run:
    export MINIMAX_API_KEY=your_key
    python examples/event_hooks_demo.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from yom import Agent
from yom.events import AgentEventType


async def demo_event_subscription():
    """Using Agent.subscribe() for event streams.
    
    Events are emitted via agent._emit() in _run_nonstream()/_run_stream().
    """
    print("=" * 60)
    print("yom Event Subscription Demo")
    print("=" * 60)
    print()
    
    agent = Agent(tools=["core"])
    
    # Subscribe to events
    events = []
    
    def on_event(event):
        events.append(event.type.name)
        data_keys = list(event.data.keys())
        print(f"  [EVENT] {event.type.name}: {data_keys}")
    
    unsub = agent.subscribe(on_event)
    
    print("Running agent...")
    try:
        result = await agent.run("Say 'hello world' in exactly those words.")
        print()
        print(f"--- Result ---")
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    print()
    
    print(f"--- Events via subscription ---")
    for event in events:
        print(f"  {event}")
    print(f"Total events: {len(events)}")
    
    unsub()
    
    return events


def demo_event_types():
    """Show all available event types."""
    print("\n" + "=" * 60)
    print("Available Event Types")
    print("=" * 60)
    print()
    
    print("AgentEventType enum values:")
    for et in AgentEventType:
        print(f"  - {et.name}")


async def main():
    print("yom Event Subscription Demo")
    print()
    print("This demo shows the Agent.subscribe() event system:")
    print("- Subscribe to events from a specific Agent instance")
    print("- Events emitted during agent lifecycle")
    print()
    
    demo_event_types()
    
    events = await demo_event_subscription()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print(f"Agent.subscribe() events: {len(events)}")
    print()
    print("Note: Event subscription works for the main agent instance.")


if __name__ == "__main__":
    asyncio.run(main())
