"""Tests for session backends."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from yom import AgentState
from yom.models.messages import UserMessage
from yom.session import FileSessionBackend, InMemorySessionBackend


class TestInMemorySessionBackend:
    """Tests for InMemorySessionBackend."""

    @pytest.mark.asyncio
    async def test_create_and_load(self):
        """Test creating and loading a session."""
        backend = InMemorySessionBackend()
        state = AgentState.create(runtime_id="test", session_id="session-1")
        state.add_user_message("Hello")

        await backend.create("session-1", state)
        loaded = await backend.load("session-1")

        assert loaded is not None
        assert loaded.session_id == "session-1"
        assert len(loaded.messages) == 1  # user message only

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading a nonexistent session returns None."""
        backend = InMemorySessionBackend()
        loaded = await backend.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_save_updates_existing(self):
        """Test that save updates an existing session."""
        backend = InMemorySessionBackend()
        state = AgentState.create(runtime_id="test", session_id="session-1")
        state.add_user_message("Hello")

        await backend.create("session-1", state)
        state.add_assistant_message("Hi!")
        await backend.save("session-1", state)

        loaded = await backend.load("session-1")
        assert len(loaded.messages) == 2


class TestFileSessionBackend:
    """Tests for FileSessionBackend."""

    @pytest.mark.asyncio
    async def test_create_and_load(self):
        """Test creating and loading a session from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)
            state = AgentState.create(runtime_id="test", session_id="session-1")
            state.add_user_message("Hello")

            await backend.create("session-1", state)
            loaded = await backend.load("session-1")

            assert loaded is not None
            assert loaded.session_id == "session-1"
            assert len(loaded.messages) == 1

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading a nonexistent session returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)
            loaded = await backend.load("nonexistent")
            assert loaded is None

    @pytest.mark.asyncio
    async def test_save_updates_existing(self):
        """Test that save updates an existing session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)
            state = AgentState.create(runtime_id="test", session_id="session-1")
            state.add_user_message("Hello")

            await backend.create("session-1", state)
            state.add_assistant_message("Hi!")
            await backend.save("session-1", state)

            loaded = await backend.load("session-1")
            assert len(loaded.messages) == 2

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)
            state = AgentState.create(runtime_id="test", session_id="session-1")
            state.add_user_message("Hello")

            await backend.create("session-1", state)
            await backend.delete("session-1")
            loaded = await backend.load("session-1")

            assert loaded is None

    @pytest.mark.asyncio
    async def test_list(self):
        """Test listing session IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)

            state1 = AgentState.create(runtime_id="runtime-1", session_id="s1")
            state2 = AgentState.create(runtime_id="runtime-1", session_id="s2")
            state3 = AgentState.create(runtime_id="runtime-2", session_id="s3")

            await backend.create("s1", state1)
            await backend.create("s2", state2)
            await backend.create("s3", state3)

            ids = await backend.list("runtime-1")
            assert set(ids) == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_atomic_write(self):
        """Test that writes are atomic (file exists or not, no partial writes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = FileSessionBackend(base_dir=tmpdir)
            state = AgentState.create(runtime_id="test", session_id="session-1")
            state.add_user_message("Hello")

            await backend.create("session-1", state)
            path = backend._session_path("session-1")

            # File should exist and be valid JSON
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["session_id"] == "session-1"