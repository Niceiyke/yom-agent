"""Sub-agent spawning support."""

from yom.subagent.core import (
    SubAgentDefinition,
    SubAgentManager,
    SubAgentRegistry,
    SubAgentRequest,
    SubAgentResult,
    SubAgentRun,
    get_default_manager,
    set_default_manager,
)
from yom.subagent.tool import SPAWN_TOOL_SCHEMA, create_catalog_tool, create_spawn_tool

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