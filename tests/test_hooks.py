"""Tests for hook system."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from yom.hooks import HookRegistry, HookResult, block, allow


class TestHookRegistry:
    """Tests for HookRegistry."""

    @pytest.mark.asyncio
    async def test_register_and_emit(self):
        """Test basic hook registration and emission."""
        hooks = HookRegistry()
        results = []

        @hooks.on("before_turn")
        async def handler(state=None, iteration=None):
            results.append(iteration)

        await hooks.emit("before_turn", iteration=1)
        assert results == [1]

    @pytest.mark.asyncio
    async def test_multiple_hooks_same_event(self):
        """Test multiple hooks for same event."""
        hooks = HookRegistry()
        results = []

        async def handler1(**kwargs):
            results.append(1)

        async def handler2(**kwargs):
            results.append(2)

        hooks.on("after_turn", handler1)
        hooks.on("after_turn", handler2)

        await hooks.emit("after_turn")

        assert set(results) == {1, 2}

    @pytest.mark.asyncio
    async def test_before_and_after_hooks(self):
        """Test before and after hooks execute in order."""
        hooks = HookRegistry()
        execution_order = []

        @hooks.on("before_turn")
        async def before(**kwargs):
            execution_order.append("before")

        @hooks.on("after_turn")
        async def after(**kwargs):
            execution_order.append("after")

        await hooks.emit("before_turn")
        await hooks.emit("after_turn")

        assert execution_order == ["before", "after"]

    @pytest.mark.asyncio
    async def test_hook_exception_accumulated(self):
        """Test that hook exceptions are accumulated."""
        hooks = HookRegistry(fail_fast=False)

        @hooks.on("before_turn")
        async def bad_handler(**kwargs):
            raise ValueError("Test error")

        await hooks.emit("before_turn")

        assert len(hooks.errors) == 1
        assert isinstance(hooks.errors[0], ValueError)

    @pytest.mark.asyncio
    async def test_fail_fast_raises(self):
        """Test that fail_fast=True raises on exception."""
        hooks = HookRegistry(fail_fast=True)

        @hooks.on("before_turn")
        async def bad_handler(**kwargs):
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await hooks.emit("before_turn")

    @pytest.mark.asyncio
    async def test_emit_returns_last_result(self):
        """Test that emit returns last hook result."""
        hooks = HookRegistry()

        @hooks.on("after_turn")
        async def handler1(**kwargs):
            return "first"

        @hooks.on("after_turn")
        async def handler2(**kwargs):
            return "second"

        result = await hooks.emit("after_turn")
        assert result == "second"

    @pytest.mark.asyncio
    async def test_decorator_shortcut(self):
        """Test decorator shortcuts like @hooks.before_turn."""
        hooks = HookRegistry()
        results = []

        @hooks.before_turn
        async def handler(state=None, iteration=None):
            results.append(iteration)

        await hooks.emit("before_turn", iteration=42)
        assert results == [42]

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all hooks."""
        hooks = HookRegistry()

        @hooks.on("before_turn")
        async def handler(**kwargs):
            pass

        hooks.clear()

        # All hook lists should be empty
        assert len(hooks._hooks["before_turn"]) == 0
        assert len(hooks._before_hooks["before_turn"]) == 0
        assert len(hooks._after_hooks["before_turn"]) == 0

    @pytest.mark.asyncio
    async def test_emit_with_result(self):
        """Test emit_with_result returns blocked flag."""
        hooks = HookRegistry()

        @hooks.on("before_tool_call")
        async def handler(**kwargs):
            return HookResult(value="result", blocked=True)

        result, blocked = await hooks.emit_with_result("before_tool_call")

        assert result.value == "result"
        assert blocked is True

    @pytest.mark.asyncio
    async def test_list_copy_safe_during_iteration(self):
        """Test that emitting during registration doesn't cause issues."""
        hooks = HookRegistry()
        results = []

        async def add_and_emit():
            await asyncio.sleep(0.01)
            hooks.on("before_turn", lambda **kwargs: results.append("added"))
            await hooks.emit("before_turn")

        # Register first handler that will trigger add_and_emit
        async def trigger(**kwargs):
            asyncio.create_task(add_and_emit())

        hooks.on("before_turn", trigger)
        await hooks.emit("before_turn")
        await asyncio.sleep(0.05)  # Give time for async operations

        # Should not raise and should have results from both hooks
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_unknown_hook_raises(self):
        """Test that emitting unknown hook raises ValueError."""
        hooks = HookRegistry()

        with pytest.raises(ValueError, match="Unknown hook"):
            await hooks.emit("nonexistent_hook")


class TestHookResult:
    """Tests for HookResult class."""

    def test_block_result(self):
        """Test creating a blocking result."""
        result = HookResult(value="data", blocked=True)
        assert result.value == "data"
        assert result.__blocked__ is True

    def test_allow_result(self):
        """Test creating an allowing result."""
        result = HookResult(value="data", blocked=False)
        assert result.value == "data"
        assert result.__blocked__ is False

    def test_default_blocked_is_false(self):
        """Test that default blocked is False."""
        result = HookResult(value="data")
        assert result.__blocked__ is False


class TestBlockAllow:
    """Tests for block/allow helper functions."""

    def test_block_function(self):
        """Test block() creates blocked result."""
        result = block()
        assert result.__blocked__ is True

    def test_allow_function(self):
        """Test allow() creates allowed result."""
        result = allow()
        assert result.__blocked__ is False


class TestGlobalHooks:
    """Tests for global_hooks singleton."""

    def test_global_hooks_exists(self):
        """Test that global_hooks exists and is a HookRegistry."""
        from yom.hooks import global_hooks

        assert isinstance(global_hooks, HookRegistry)

    def test_global_hooks_can_register(self):
        """Test that global_hooks accepts registrations."""
        from yom.hooks import global_hooks

        @global_hooks.on("agent_start")
        async def handler(**kwargs):
            pass

        assert len(global_hooks._hooks["agent_start"]) >= 1

        # Clean up
        global_hooks.clear()