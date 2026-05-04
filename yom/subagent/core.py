"""Sub-agent management for spawning specialized agents."""

from __future__ import annotations

import asyncio
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yom.models import AgentState
from yom.runtime.config import RuntimeSettings
from yom.runtime.factories import build_runtime


PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s", re.IGNORECASE),
    re.compile(r"you\s+are\s+a\s", re.IGNORECASE),
    re.compile(r"(new\s+)?system\s+prompt\s*:", re.IGNORECASE),
    re.compile(r"override\s+instructions?", re.IGNORECASE),
    re.compile(r"ignore\s+all", re.IGNORECASE),
]


def _sanitize_context(context: str) -> str:
    """Remove potential prompt injection attempts from context."""
    sanitized_lines = []
    for line in context.splitlines():
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(line):
                return "[redacted due to potential prompt injection]"
        sanitized_lines.append(line)
    return "\n".join(sanitized_lines)


def build_subagent_prompt(task: str, context: str = "") -> str:
    """Build prompt for sub-agent with optional context."""
    if context:
        sanitized = _sanitize_context(context)
        return f"Context from parent:\n{sanitized}\n\nYour task:\n{task}"
    return task


@dataclass
class SubAgentRequest:
    """Request to spawn a sub-agent."""
    agent_type: str
    task: str
    context: str = ""
    model: str | None = None
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubAgentRun:
    """Record of an active sub-agent run."""
    run_id: str
    parent_id: str
    child_id: str
    agent_type: str
    task: str
    started_at: float
    status: str = "running"


@dataclass
class SubAgentResult:
    """Result from a sub-agent run."""
    child_id: str
    agent_type: str
    status: str
    summary: str
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    token_usage: dict[str, int] | None = None


@dataclass
class SubAgentDefinition:
    """Definition of a spawnable sub-agent (metadata + path to full prompt)."""
    name: str
    description: str
    mode: str = "subagent"  # "subagent" or "primary"
    tools: list[str] | None = None
    model: str | None = None
    path: Path | None = None
    prompt: str | None = None  # Set on lazy load

    def load_prompt(self) -> str:
        """Load full prompt from file if not already loaded."""
        if self.prompt is None and self.path:
            text = self.path.read_text(encoding="utf-8")
            self.prompt = self._extract_prompt(text)
        return self.prompt or ""

    @staticmethod
    def _extract_prompt(text: str) -> str:
        """Extract prompt body from markdown (after frontmatter)."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return text.strip()

    @classmethod
    def from_markdown(cls, path: Path) -> SubAgentDefinition:
        """Parse a markdown file into a SubAgentDefinition."""
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError(f"{path} is missing frontmatter")

        try:
            _, frontmatter, body = text.split("---", 2)
        except ValueError as exc:
            raise ValueError(f"{path} has invalid frontmatter") from exc

        data = cls._parse_frontmatter(frontmatter)

        name = data.get("name")
        if not name:
            raise ValueError(f"{path} is missing required 'name' field")

        return cls(
            name=name,
            description=data.get("description", ""),
            mode=data.get("mode", "subagent"),
            tools=data.get("tools"),
            model=data.get("model"),
            path=path,
            prompt=body.strip(),
        )

    @staticmethod
    def _parse_frontmatter(frontmatter: str) -> dict[str, Any]:
        """Parse YAML-like frontmatter."""
        data: dict[str, Any] = {}
        current_list_key: str | None = None

        for raw_line in frontmatter.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue
            if line.startswith("  - ") and current_list_key:
                value = line[4:].strip()
                if isinstance(data.get(current_list_key), list):
                    data[current_list_key].append(value)
                continue

            current_list_key = None
            if ":" not in line:
                continue

            key, raw_value = line.split(":", 1)
            key = key.strip()
            value = raw_value.strip()
            if not value:
                data[key] = []
                current_list_key = key
            else:
                data[key] = value

        return data


class SubAgentRegistry:
    """Registry of available sub-agents with lazy-loading prompts."""

    def __init__(self):
        self._agents: dict[str, SubAgentDefinition] = {}
        self._agents_dir: Path | None = None

    def register(self, definition: SubAgentDefinition) -> None:
        """Register a sub-agent definition."""
        self._agents[definition.name] = definition

    def get(self, name: str) -> SubAgentDefinition | None:
        """Get a sub-agent definition by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def get_catalog(self) -> list[dict]:
        """Get name/description catalog for LLM context."""
        return [
            {"name": name, "description": agent.description}
            for name, agent in self._agents.items()
        ]

    def get_catalog_text(self) -> str:
        """Get human-readable catalog for LLM context."""
        if not self._agents:
            return "No sub-agents available."
        lines = ["Available sub-agents:"]
        for name, agent in sorted(self._agents.items()):
            lines.append(f"- {name}: {agent.description}")
        return "\n".join(lines)

    def load_from_directory(self, directory: str | Path) -> None:
        """Load all .md files from a directory as sub-agent definitions."""
        self._agents_dir = Path(directory)
        if not self._agents_dir.exists():
            return

        for path in sorted(self._agents_dir.glob("*.md")):
            try:
                definition = SubAgentDefinition.from_markdown(path)
                if definition.name != path.stem:
                    raise ValueError(f"Agent name '{definition.name}' must match filename '{path.stem}'")
                if definition.mode != "subagent":
                    continue  # Skip non-spawnable agents (e.g., mode="primary")
                self.register(definition)
            except Exception as exc:
                print(f"Warning: Failed to load agent from {path}: {exc}")
                continue

    def register_function(self, name: str, description: str, system_prompt: str, tools: list[str] | None = None, mode: str = "subagent") -> None:
        """Convenience method to register a function-based sub-agent."""
        if mode != "subagent":
            return  # Skip non-spawnable agents
        self.register(SubAgentDefinition(
            name=name,
            description=description,
            mode=mode,
            tools=tools,
            prompt=system_prompt,
            path=None,
        ))


class SubAgentManager:
    """Manages spawning and running of sub-agents."""

    def __init__(
        self,
        *,
        max_depth: int = 4,
        max_subagent_runs: int = 16,
        max_children_per_parent: int = 4,
        default_timeout_seconds: float = 300.0,
        registry: SubAgentRegistry | None = None,
    ) -> None:
        self.max_depth = max_depth
        self.max_subagent_runs = max_subagent_runs
        self.max_children_per_parent = max_children_per_parent
        self.default_timeout_seconds = default_timeout_seconds
        self.registry = registry or SubAgentRegistry()

        self._active_runs: dict[str, tuple[SubAgentRun, asyncio.Task[str]]] = {}
        self._parent_children: dict[str, set[str]] = {}

    @property
    def active_run_count(self) -> int:
        return len(self._active_runs)

    def get_active_children(self, parent_id: str) -> list[SubAgentRun]:
        child_ids = self._parent_children.get(parent_id, set())
        return [run for run_id, (run, _) in self._active_runs.items() if run_id in child_ids]

    async def run(self, request: SubAgentRequest, parent_state: AgentState | None = None) -> SubAgentResult:
        """Run a sub-agent with the given request."""
        started_at = time.monotonic()

        parent_id = parent_state.runtime_id if parent_state else "main"
        parent_depth = parent_state.metadata.get("depth", 0) if parent_state else 0

        run_id = f"run_{parent_id[:8]}_{int(started_at * 1000)}"
        child_id = f"child_{run_id}"

        if len(self._active_runs) >= self.max_subagent_runs:
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="failed",
                summary="[LIMIT] Global sub-agent run limit reached.",
                started_at=started_at,
                finished_at=time.monotonic(),
            )

        parent_children = self._parent_children.setdefault(parent_id, set())
        if len(parent_children) >= self.max_children_per_parent:
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="failed",
                summary="[LIMIT] Per-parent child limit reached.",
                started_at=started_at,
                finished_at=time.monotonic(),
            )

        if parent_depth + 1 >= self.max_depth:
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="failed",
                summary="[DEPTH LIMIT] Max sub-agent depth reached.",
                started_at=started_at,
                finished_at=time.monotonic(),
            )

        agent_def = self.registry.get(request.agent_type)
        if agent_def is None:
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="failed",
                summary=f"Tool error: Unknown sub-agent type: {request.agent_type}",
                started_at=started_at,
                finished_at=time.monotonic(),
            )

        from yom.tools import CORE_TOOLS
        sub_tools = list(CORE_TOOLS)

        if agent_def.tools:
            for tool_name in agent_def.tools:
                if tool_name == "core":
                    continue
                for t in CORE_TOOLS:
                    name = getattr(t, "_tool_name", None) or getattr(t, "name", None)
                    if name == tool_name:
                        sub_tools.append(t)
                        break

        # Load full prompt on demand
        full_prompt = agent_def.load_prompt()
        prompt = build_subagent_prompt(request.task, request.context)
        if full_prompt:
            prompt = f"{full_prompt}\n\n{prompt}"

        depth = parent_depth + 1

        sub_state = AgentState.create(
            runtime_id=f"{parent_id}-child",
            system_prompt=prompt,
            max_turns=50,
        )
        sub_state.metadata["depth"] = depth
        sub_state.metadata["parent_id"] = parent_id
        sub_state.metadata["agent_type"] = request.agent_type

        run_record = SubAgentRun(
            run_id=run_id,
            parent_id=parent_id,
            child_id=child_id,
            agent_type=request.agent_type,
            task=request.task,
            started_at=started_at,
        )
        parent_children.add(run_id)

        timeout_seconds = request.timeout_seconds if request.timeout_seconds else self.default_timeout_seconds

        async def run_child() -> str:
            settings = RuntimeSettings(
                runtime_id=child_id,
                system_prompt=prompt,
                tools=sub_tools,
                default_model=agent_def.model or request.model,
            )
            runtime = build_runtime(settings, mode="yom_agent")
            result = await runtime.run_prompt(prompt=request.task)
            return result.final_message or result.error or ""

        task = asyncio.create_task(run_child())
        self._active_runs[run_id] = (run_record, task)

        finished_at = time.monotonic()
        status = "failed"
        result = ""

        try:
            result = await asyncio.wait_for(task, timeout=timeout_seconds)
            finished_at = time.monotonic()
            status = "succeeded"
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            finished_at = time.monotonic()
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="timeout",
                summary=f"[TIMEOUT] Child run timed out after {timeout_seconds}s.",
                started_at=started_at,
                finished_at=finished_at,
            )
        except asyncio.CancelledError:
            task.cancel()
            finished_at = time.monotonic()
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="cancelled",
                summary="[CANCELLED]",
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception as exc:
            task.cancel()
            finished_at = time.monotonic()
            return SubAgentResult(
                child_id=child_id,
                agent_type=request.agent_type,
                status="failed",
                summary=f"[ERROR] {exc}",
                started_at=started_at,
                finished_at=finished_at,
            )
        finally:
            self._cleanup_run(run_id, parent_id)

        return SubAgentResult(
            child_id=child_id,
            agent_type=request.agent_type,
            status=status,
            summary=_normalize_summary(result, request.agent_type),
            started_at=started_at,
            finished_at=finished_at,
        )

    def _cleanup_run(self, run_id: str, parent_id: str) -> None:
        self._active_runs.pop(run_id, None)
        if parent_id in self._parent_children:
            self._parent_children[parent_id].discard(run_id)
            if not self._parent_children[parent_id]:
                del self._parent_children[parent_id]

    def cancel_children(self, parent_id: str) -> None:
        """Cancel all active children of a parent."""
        child_ids = list(self._parent_children.get(parent_id, set()))
        for run_id in child_ids:
            if run_id in self._active_runs:
                _, task = self._active_runs[run_id]
                task.cancel()

    def get_active_runs(self) -> list[SubAgentRun]:
        return [run for run, _ in self._active_runs.values()]


MAX_SUMMARY_LENGTH = 4000


def _normalize_summary(result: str, agent_type: str) -> str:
    """Truncate result if too long."""
    if len(result) <= MAX_SUMMARY_LENGTH:
        return result
    return result[:MAX_SUMMARY_LENGTH] + f"\n[OUTPUT TRUNCATED — original was {len(result)} chars]"


_default_manager: SubAgentManager | None = None
_default_manager_lock: threading.Lock = threading.Lock()


def get_default_manager() -> SubAgentManager:
    global _default_manager
    if _default_manager is None:
        with _default_manager_lock:
            if _default_manager is None:
                _default_manager = SubAgentManager()
    return _default_manager


def set_default_manager(manager: SubAgentManager) -> None:
    global _default_manager
    with _default_manager_lock:
        _default_manager = manager