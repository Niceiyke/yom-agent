#!/usr/bin/env python3
"""Production example: Code review pipeline with sub-agents.

This example demonstrates:
1. Loading skills at startup
2. Spawning coder and reviewer sub-agents
3. Passing context between coordinator and sub-agents
4. Session persistence for tracking

Run:
    export MINIMAX_API_KEY=your_key
    python examples/production/code_review_pipeline.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    print("=" * 60)
    print("Code Review Pipeline - Production Example")
    print("=" * 60)
    print()
    
    from yom import Agent, AgentState
    from yom.skills import load_skills, format_skills_for_prompt
    
    # Load skills
    print("Loading skills...")
    skills_dir = Path(__file__).parent.parent.parent / ".yom" / "skills"
    loaded = load_skills(cwd=skills_dir.parent, skill_paths=[skills_dir])
    print(f"  Found {len(loaded.skills)} skills: {[s.name for s in loaded.skills]}")
    
    # Format skills for system prompt
    skills_catalog = format_skills_for_prompt(loaded.skills)
    print()
    
    # Create coordinator with sub-agents
    agent = Agent(
        tools=["core", "spawn"],
        agents_dir=str(Path(__file__).parent.parent.parent / ".yom" / "agents"),
        system_prompt=f"""You coordinate a code review team.

Available sub-agents:
- coder: Writes clean Python code
- reviewer: Reviews code for bugs and issues

Workflow:
1. When asked to write code, spawn the coder agent
2. Pass the user's requirements as the task
3. Then spawn the reviewer to check the code
4. Summarize findings for the user

Be efficient - combine steps when appropriate.
""",
        session_id="code-review-demo",
    )
    
    print(f"Tools: {agent.available_tools}")
    print()
    
    # Task: Write and review a specific piece of code
    task = """Write a Python function called 'calculate_stats' that:
1. Takes a list of numbers
2. Returns a dictionary with mean, median, and standard deviation
3. Handles empty lists gracefully

After writing, have the reviewer check it for bugs."""
    
    print(f"Task: {task[:80]}...")
    print()
    print("-" * 60)
    
    result = await agent.run(task)
    
    print("\n--- Full Response ---")
    print(result)
    print()
    
    # Show events
    print("-" * 60)
    print("Session Info")
    print("-" * 60)
    messages = await agent.get_session_messages()
    print(f"Messages in session: {len(messages)}")
    
    if agent.state:
        print(f"Current turn: {agent.state.current_turn}")


if __name__ == "__main__":
    asyncio.run(main())
