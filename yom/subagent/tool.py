"""Spawn agent tool for calling sub-agents."""

from __future__ import annotations

from typing import Any

from yom.subagent.core import SubAgentManager, SubAgentRequest, get_default_manager

SPAWN_TOOL_SCHEMA: dict[str, Any] = {
    "name": "spawn_agent",
    "description": "Spawn a sub-agent to handle specialized tasks. The sub-agent runs independently and returns a summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "Sub-agent type/name (e.g., 'reviewer', 'coder', 'explainer')",
            },
            "task": {
                "type": "string",
                "description": "Specific task for the sub-agent to complete",
            },
            "context": {
                "type": "string",
                "description": "Optional context from parent agent needed for the task",
            },
            "model": {
                "type": "string",
                "description": "Optional model override for this sub-agent",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Optional timeout for this run",
            },
        },
        "required": ["type", "task"],
    },
}


def make_spawn_agent_tool(
    manager: SubAgentManager | None = None,
):
    """Create the spawn_agent tool function."""
    if manager is None:
        manager = get_default_manager()

    async def spawn_agent(input_data: dict[str, Any], parent_state: Any) -> str:
        """Spawn a sub-agent and return its summary."""
        agent_name = input_data.get("type")
        task = input_data.get("task")

        if not isinstance(agent_name, str) or not agent_name:
            return "Tool error: type must be a non-empty string"
        if not isinstance(task, str) or not task:
            return "Tool error: task must be a non-empty string"

        request = SubAgentRequest(
            agent_type=agent_name,
            task=task,
            context=input_data.get("context", ""),
            model=input_data.get("model"),
            timeout_seconds=input_data.get("timeout_seconds"),
        )

        result = await manager.run(request, parent_state)
        return result.summary

    return spawn_agent, SPAWN_TOOL_SCHEMA


def create_spawn_tool(manager: SubAgentManager | None = None):
    """Create spawn_agent tool for use with Agent."""
    tool_fn, schema = make_spawn_agent_tool(manager)

    async def spawn_tool(type: str, task: str, context: str = "", model: str = "", timeout_seconds: float = 0) -> str:
        input_data = {
            "type": type,
            "task": task,
            "context": context,
            "model": model or None,
            "timeout_seconds": timeout_seconds or None,
        }
        return await tool_fn(input_data, None)

    spawn_tool._tool_name = "spawn_agent"  # type: ignore[attr-defined]
    spawn_tool._tool_description = SPAWN_TOOL_SCHEMA["description"]  # type: ignore[attr-defined]
    spawn_tool._tool_parameters = SPAWN_TOOL_SCHEMA["input_schema"]  # type: ignore[attr-defined]

    return spawn_tool


def create_catalog_tool(manager: SubAgentManager | None = None):
    """Create a tool that returns the sub-agent catalog."""
    if manager is None:
        manager = get_default_manager()

    async def get_catalog(input_data: dict[str, Any], parent_state: Any) -> str:
        """Return the list of available sub-agents."""
        return manager.registry.get_catalog_text()

    catalog_tool = get_catalog
    catalog_tool._tool_name = "list_subagents"  # type: ignore[attr-defined]
    catalog_tool._tool_description = "List available sub-agents that can be spawned."  # type: ignore[attr-defined]
    catalog_tool._tool_parameters = {  # type: ignore[attr-defined]
        "type": "object",
        "properties": {},
        "required": [],
    }

    return catalog_tool