"""Session backend interface and implementations."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yom.models import AgentState


SESSION_VERSION = 1
SCHEMA_VERSION_KEY = "_schema_version"


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

    async def cleanup_expired(self, max_age_seconds: float) -> int:
        """Remove sessions older than max_age_seconds. Returns count of deleted."""
        return 0


class InMemorySessionBackend(SessionBackend):
    """Ephemeral in-memory session storage (for testing/ephemeral use)."""

    def __init__(self, ttl_seconds: float | None = None):
        self._sessions: dict[str, tuple[AgentState, float]] = {}
        self._ttl_seconds = ttl_seconds

    def _is_expired(self, timestamp: float) -> bool:
        if self._ttl_seconds is None:
            return False
        return (time.time() - timestamp) > self._ttl_seconds

    async def create(self, session_id: str, state: AgentState) -> None:
        self._sessions[session_id] = (state, time.time())

    async def load(self, session_id: str) -> AgentState | None:
        entry = self._sessions.get(session_id)
        if entry is None:
            return None
        state, timestamp = entry
        if self._is_expired(timestamp):
            await self.delete(session_id)
            return None
        return state

    async def save(self, session_id: str, state: AgentState) -> None:
        self._sessions[session_id] = (state, time.time())

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def list(self, runtime_id: str) -> list[str]:
        expired = []
        result = []
        for sid, (state, ts) in self._sessions.items():
            if self._is_expired(ts):
                expired.append(sid)
            elif state.runtime_id == runtime_id:
                result.append(sid)
        for sid in expired:
            del self._sessions[sid]
        return result

    async def cleanup_expired(self, max_age_seconds: float) -> int:
        now = time.time()
        to_delete = []
        for sid, (_, ts) in self._sessions.items():
            if (now - ts) > max_age_seconds:
                to_delete.append(sid)
        for sid in to_delete:
            del self._sessions[sid]
        return len(to_delete)


class FileSessionBackend(SessionBackend):
    """File-based session storage (JSON files with atomic writes)."""

    def __init__(
        self,
        base_dir: str | Path = Path("./sessions"),
        ttl_seconds: float | None = None,
        max_history_messages: int | None = None,
    ):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._ttl_seconds = ttl_seconds
        self._max_history_messages = max_history_messages
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_interval = 300.0

    def _session_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}.json"

    def _atomic_write(self, path: Path, data: dict) -> None:
        """Write data atomically using temp file + rename."""
        dir_path = str(path.parent)
        with tempfile.NamedTemporaryFile(mode="w", dir=dir_path, delete=False, suffix=".tmp") as f:
            json.dump(data, f)
            temp_path = f.name
        Path(temp_path).rename(path)

    def _add_schema_version(self, data: dict) -> dict:
        """Add schema version to data."""
        result = dict(data)
        result[SCHEMA_VERSION_KEY] = SESSION_VERSION
        return result

    def _migrate_data(self, data: dict) -> dict:
        """Migrate data from older schema versions."""
        version = data.get(SCHEMA_VERSION_KEY, 0)
        if version >= SESSION_VERSION:
            return data

        result = dict(data)

        if version < 1:
            if "messages" in result and "created_at" in result:
                if isinstance(result["created_at"], str):
                    result["created_at"] = result["created_at"]
                if "updated_at" not in result:
                    result["updated_at"] = result["created_at"]

        result[SCHEMA_VERSION_KEY] = SESSION_VERSION
        return result

    def _truncate_history(self, state: AgentState) -> AgentState:
        """Truncate message history if max_history_messages is set."""
        if self._max_history_messages is None:
            return state
        if len(state.messages) <= self._max_history_messages:
            return state

        preserved = self._max_history_messages // 2
        kept_messages = state.messages[-preserved:]
        summary_msg = {
            "role": "system",
            "content": f"[Previous {len(state.messages) - preserved} messages truncated]",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"_truncated": True},
        }
        from yom.models.messages import SystemMessage
        state.messages = [SystemMessage(content=str(summary_msg["content"]))] + kept_messages
        return state

    async def create(self, session_id: str, state: AgentState) -> None:
        path = self._session_path(session_id)
        data = state.to_dict()
        data = self._add_schema_version(data)
        self._atomic_write(path, data)

    async def load(self, session_id: str) -> AgentState | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None

        try:
            stat = path.stat()
            if self._ttl_seconds is not None:
                age = time.time() - stat.st_mtime
                if age > self._ttl_seconds:
                    await self.delete(session_id)
                    return None

            data = json.loads(path.read_text())
            data = self._migrate_data(data)
            data.pop(SCHEMA_VERSION_KEY, None)
            from yom.models.state import AgentState
            return AgentState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    async def save(self, session_id: str, state: AgentState) -> None:
        state = self._truncate_history(state)
        path = self._session_path(session_id)
        data = state.to_dict()
        data = self._add_schema_version(data)
        self._atomic_write(path, data)

    async def delete(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    async def list(self, runtime_id: str) -> list[str]:
        sids = []
        now = time.time()
        to_delete = []
        for path in self.base_dir.glob("*.json"):
            try:
                stat = path.stat()
                if self._ttl_seconds is not None and (now - stat.st_mtime) > self._ttl_seconds:
                    to_delete.append(path)
                    continue
                data = json.loads(path.read_text())
                data = self._migrate_data(data)
                if data.get("runtime_id") == runtime_id:
                    sids.append(path.stem)
            except Exception:
                continue
        for path in to_delete:
            path.unlink()
        return sids

    async def cleanup_expired(self, max_age_seconds: float) -> int:
        """Remove sessions older than max_age_seconds."""
        now = time.time()
        deleted = 0
        for path in self.base_dir.glob("*.json"):
            try:
                stat = path.stat()
                if (now - stat.st_mtime) > max_age_seconds:
                    path.unlink()
                    deleted += 1
            except Exception:
                continue
        return deleted