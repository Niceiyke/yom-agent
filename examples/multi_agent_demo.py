#!/usr/bin/env python3
"""Production multi-agent demo with real LLM.

This example demonstrates:
- Sub-agents spawned from Markdown definitions
- Skills loaded on demand
- Session persistence
- Event tracking
- Real LLM calls

Features:
- Rate limiting between calls
- Retry logic for rate limit errors
- Graceful error handling

Run:
    export MINIMAX_API_KEY=your_key  # or OPENAI_API_KEY
    python examples/multi_agent_demo.py
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Add project root to path for local development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Rate limiting: minimum seconds between LLM calls
MIN_DELAY_BETWEEN_CALLS = 2.0
# Delay after spawning a sub-agent
DELAY_AFTER_SPAWN = 1.0


class RateLimitedAgent:
    """Wrapper that adds rate limiting to an agent."""
    
    def __init__(self, agent):
        self.agent = agent
        self._last_call_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < MIN_DELAY_BETWEEN_CALLS:
            sleep_time = MIN_DELAY_BETWEEN_CALLS - elapsed
            print(f"  [Rate limit] Sleeping {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        self._last_call_time = time.time()
    
    async def run(self, prompt: str, max_retries: int = 3) -> str:
        """Run with rate limiting and retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            self._rate_limit()
            
            try:
                result = await self.agent.run(prompt)
                return result
                
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()
                
                if "rate_limit" in error_str or "429" in error_str:
                    print(f"  [Rate limit] Got 429, waiting {2 ** attempt * 2}s...")
                    time.sleep(2 ** attempt * 2)  # Exponential backoff
                    continue
                    
                if "timeout" in error_str:
                    print(f"  [Timeout] Attempt {attempt + 1} failed, retrying...")
                    time.sleep(2 ** attempt)
                    continue
                
                # Other error, don't retry
                raise
        
        raise RuntimeError(f"Failed after {max_retries} retries: {last_error}")


async def run_demo(model: str | None = None, session_id: str = "demo-session"):
    """Run the multi-agent demo with rate limiting."""
    from yom import Agent
    
    print("=" * 60)
    print("yom Multi-Agent Production Demo")
    print("=" * 60)
    print()
    
    # Track events
    events_log = []
    
    def track_event(event):
        events_log.append(event.type.name)
        print(f"  [EVENT] {event.type.name}")
    
    # Create coordinator agent with sub-agents
    print("Setting up agent with sub-agents...")
    
    agent = Agent(
        tools=["core", "spawn"],
        agents_dir=str(project_root / ".yom" / "agents"),
        system_prompt="""You are a helpful coordinator that manages a team of specialists.

Available sub-agents:
- reviewer: Reviews Python code for bugs and issues
- coder: Writes clean Python code

When asked to write code, spawn the coder agent.
When asked to review code, spawn the reviewer agent.

Use spawn_agent to dispatch tasks. Be specific about what you want done.""",
        session_id=session_id,
        model=model,
    )
    
    # Wrap with rate limiting
    rate_limited = RateLimitedAgent(agent)
    
    # Subscribe to events
    agent.subscribe(track_event)
    
    print(f"Agent created with tools: {agent.available_tools}")
    print(f"Session ID: {agent.session_id}")
    print()
    
    try:
        # Demo 1: Simple code generation
        print("-" * 60)
        print("Demo 1: Generate code via coder sub-agent")
        print("-" * 60)
        
        result1 = await rate_limited.run(
            """Write a Python function called 'greet' that takes a name and returns "Hello, {name}!"."""
        )
        
        print("\n--- Result ---")
        print(result1)
        print()
        
        # Give the API a moment to breathe
        time.sleep(DELAY_AFTER_SPAWN)
        
        # Demo 2: Code review
        print("-" * 60)
        print("Demo 2: Review code via reviewer sub-agent")
        print("-" * 60)
        
        code_to_review = '''
def get_user(uid):
    import db
    return db.query(f"SELECT * FROM users WHERE id={uid}")
'''
        
        result2 = await rate_limited.run(
            f"""Review this Python code for security issues:\n\n{code_to_review}"""
        )
        
        print("\n--- Result ---")
        print(result2)
        print()
        
        # Summary
        print("-" * 60)
        print("Summary")
        print("-" * 60)
        print(f"Total events tracked: {len(events_log)}")
        print(f"Event types: {set(events_log)}")
        print(f"Session ID: {agent.session_id}")
        
        # Show session messages
        messages = await agent.get_session_messages()
        print(f"Messages in session: {len(messages)}")
        
    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        print("This is likely due to rate limiting. Try running with fewer demos.")
        raise


async def run_simple_demo():
    """Simple demo without sub-agents."""
    from yom import Agent
    
    print("=" * 60)
    print("yom Simple Demo (no sub-agents)")
    print("=" * 60)
    print()
    
    agent = Agent(
        tools=["core"],
        system_prompt="You are a helpful assistant that writes clean Python code.",
    )
    
    result = await agent.run("Write a function to reverse a string and write it to demo.py.")
    print("\n--- Result ---")
    print(result)
    print()


def main():
    parser = argparse.ArgumentParser(description="yom multi-agent demo")
    parser.add_argument(
        "--model",
        help="Model to use (e.g., MiniMax-M2.7, gpt-4o-mini)",
        default=os.environ.get("YOM_MODEL", None),
    )
    parser.add_argument(
        "--session",
        help="Session ID for persistence",
        default="demo-session",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run simple demo without sub-agents",
    )
    
    args = parser.parse_args()
    
    if args.simple:
        asyncio.run(run_simple_demo())
    else:
        asyncio.run(run_demo(model=args.model, session_id=args.session))


if __name__ == "__main__":
    main()