"""Sub-agent spawning support."""

from yom.subagent.core import (
    SubAgentManager,
    SubAgentRequest,
    SubAgentResult,
    SubAgentDefinition,
    SubAgentRegistry,
    SubAgentRun,
    get_default_manager,
    set_default_manager,
)
from yom.subagent.tool import create_spawn_tool, create_catalog_tool, SPAWN_TOOL_SCHEMA

__all__ = [
    "SubAgentManager",
    "SubAgentRequest",
    "SubAgentResult",
    "SubAgentDefinition",
    "SubAgentRegistry",
    "SubAgentRun",
    "get_default_manager",
    "set_default_manager",
    "create_spawn_tool",
    "create_catalog_tool",
    "SPAWN_TOOL_SCHEMA",
]