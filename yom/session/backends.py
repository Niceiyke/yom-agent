"""Session backend interface and implementations."""

from __future__ import annotations

import json
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yom.models import AgentState


class SessionBackend(ABC):
    """Abstract interface for session storage."""

    @abstractmethod
    async def create(self, session_id: str, state: AgentState) -> None:
        """Create a new session."""
        ...

    @abstractmethod
    async def load(self, session_id: str) -> AgentState | None:
        """Load a session by ID."""
        ...

    @abstractmethod
    async def save(self, session_id: str, state: AgentState) -> None:
        """Save a session."""
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        ...

    @abstractmethod
    async def list(self, runtime_id: str) -> list[str]:
        """List session IDs for a runtime."""
        ...


class InMemorySessionBackend(SessionBackend):
    """Ephemeral in-memory session storage (for testing/ephemeral use)."""

    def __init__(self):
        self._sessions: dict[str, AgentState] = {}

    async def create(self, session_id: str, state: AgentState) -> None:
        self._sessions[session_id] = state

    async def load(self, session_id: str) -> AgentState | None:
        return self._sessions.get(session_id)

    async def save(self, session_id: str, state: AgentState) -> None:
        self._sessions[session_id] = state

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def list(self, runtime_id: str) -> list[str]:
        return [
            sid for sid, state in self._sessions.items()
            if state.runtime_id == runtime_id
        ]


class FileSessionBackend(SessionBackend):
    """File-based session storage (JSON files with atomic writes)."""

    def __init__(self, base_dir: str | Path = Path("./sessions")):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Write data atomically using temp file + rename."""
        dir_path = str(path.parent)
        with tempfile.NamedTemporaryFile(mode="w", dir=dir_path, delete=False, suffix=".tmp") as f:
            json.dump(data, f)
            temp_path = f.name
        Path(temp_path).rename(path)

    async def create(self, session_id: str, state: AgentState) -> None:
        path = self._session_path(session_id)
        self._atomic_write(path, state.to_dict())

    async def load(self, session_id: str) -> AgentState | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        from yom.models.state import AgentState
        return AgentState.from_dict(data)

    async def save(self, session_id: str, state: AgentState) -> None:
        path = self._session_path(session_id)
        self._atomic_write(path, state.to_dict())

    async def delete(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    async def list(self, runtime_id: str) -> list[str]:
        sids = []
        for path in self.base_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("runtime_id") == runtime_id:
                    sids.append(path.stem)
            except Exception:
                continue
        return sids