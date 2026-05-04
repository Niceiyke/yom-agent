"""Async hook registry for observing runtime events."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

HookFn = Callable[..., Any]


HOOK_NAMES = {
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "before_turn",
    "after_turn",
    "message_start",
    "message_end",
    "before_tool_call",
    "after_tool_call",
    "on_tool_call",
    "on_tool_result",
    "tool_execution_start",
    "tool_execution_end",
    "on_agent_spawn",
    "on_agent_done",
    "on_error",
    "session_start",
    "session_end",
}


@dataclass
class HookRegistry:
    """Registry for managing event hooks.

    Usage:
        hooks = HookRegistry()

        @hooks.before_turn
        async def on_before_turn(state, iteration):
            print(f"Turn {iteration} starting")

        @hooks.on_tool_call
        async def on_tool(state, call):
            print(f"Tool called: {call.name}")

        # Emit events
        await hooks.emit("before_turn", state=state, iteration=1)
    """
    fail_fast: bool = False
    _hooks: dict[str, list[HookFn]] = field(default_factory=lambda: {name: [] for name in HOOK_NAMES})
    _before_hooks: dict[str, list[HookFn]] = field(default_factory=lambda: {name: [] for name in HOOK_NAMES})
    _after_hooks: dict[str, list[HookFn]] = field(default_factory=lambda: {name: [] for name in HOOK_NAMES})
    errors: list[Exception] = field(default_factory=list)

    def register(self, name: str, fn: HookFn) -> HookFn:
        """Register a hook function for an event."""
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")
        self._hooks[name].append(fn)
        return fn

    def before(self, name: str, fn: HookFn | None = None) -> HookFn:
        """Decorator to register a function to run BEFORE an event."""
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}")
        if fn is None:
            def decorator(inner: HookFn) -> HookFn:
                self._before_hooks[name].append(inner)
                return inner
            return decorator
        self._before_hooks[name].append(fn)
        return fn

    def after(self, name: str, fn: HookFn | None = None) -> HookFn:
        """Decorator to register a function to run AFTER an event."""
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}")
        if fn is None:
            def decorator(inner: HookFn) -> HookFn:
                self._after_hooks[name].append(inner)
                return inner
            return decorator
        self._after_hooks[name].append(fn)
        return fn

    def on(self, name: str, fn: HookFn | None = None) -> HookFn:
        """Decorator to register a function for an event (shorthand)."""
        if fn is None:
            def decorator(inner: HookFn) -> HookFn:
                return self.register(name, inner)
            return decorator
        return self.register(name, fn)

    def agent_start(self, fn: HookFn) -> HookFn:
        """Decorator: agent_start event."""
        return self.register("agent_start", fn)

    def agent_end(self, fn: HookFn) -> HookFn:
        """Decorator: agent_end event."""
        return self.register("agent_end", fn)

    def turn_start(self, fn: HookFn) -> HookFn:
        """Decorator: turn_start event."""
        return self.register("turn_start", fn)

    def turn_end(self, fn: HookFn) -> HookFn:
        """Decorator: turn_end event."""
        return self.register("turn_end", fn)

    def before_turn(self, fn: HookFn) -> HookFn:
        """Decorator: before_turn event."""
        return self.register("before_turn", fn)

    def after_turn(self, fn: HookFn) -> HookFn:
        """Decorator: after_turn event."""
        return self.register("after_turn", fn)

    def message_start(self, fn: HookFn) -> HookFn:
        """Decorator: message_start event."""
        return self.register("message_start", fn)

    def message_end(self, fn: HookFn) -> HookFn:
        """Decorator: message_end event."""
        return self.register("message_end", fn)

    def before_tool_call(self, fn: HookFn) -> HookFn:
        """Decorator: before_tool_call event."""
        return self.register("before_tool_call", fn)

    def after_tool_call(self, fn: HookFn) -> HookFn:
        """Decorator: after_tool_call event."""
        return self.register("after_tool_call", fn)

    def on_tool_call(self, fn: HookFn) -> HookFn:
        """Decorator: on_tool_call event."""
        return self.register("on_tool_call", fn)

    def on_tool_result(self, fn: HookFn) -> HookFn:
        """Decorator: on_tool_result event."""
        return self.register("on_tool_result", fn)

    def tool_execution_start(self, fn: HookFn) -> HookFn:
        """Decorator: tool_execution_start event."""
        return self.register("tool_execution_start", fn)

    def tool_execution_end(self, fn: HookFn) -> HookFn:
        """Decorator: tool_execution_end event."""
        return self.register("tool_execution_end", fn)

    def on_agent_spawn(self, fn: HookFn) -> HookFn:
        """Decorator: on_agent_spawn event."""
        return self.register("on_agent_spawn", fn)

    def on_agent_done(self, fn: HookFn) -> HookFn:
        """Decorator: on_agent_done event."""
        return self.register("on_agent_done", fn)

    def on_error(self, fn: HookFn) -> HookFn:
        """Decorator: on_error event."""
        return self.register("on_error", fn)

    def session_start(self, fn: HookFn) -> HookFn:
        """Decorator: session_start event."""
        return self.register("session_start", fn)

    def session_end(self, fn: HookFn) -> HookFn:
        """Decorator: session_end event."""
        return self.register("session_end", fn)

    async def emit(self, name: str, **payload: Any) -> Any:
        """Emit an event, calling all registered hooks.

        Args:
            name: Event name (e.g., "before_turn")
            **payload: Arguments to pass to hook functions

        Returns:
            Result from the last registered hook, or None
        """
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")

        for fn in list(self._before_hooks.get(name, [])):
            try:
                result = fn(**payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        result = None
        for fn in list(self._hooks[name]):
            try:
                result = fn(**payload)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        for fn in list(self._after_hooks.get(name, [])):
            try:
                after_result = fn(**payload)
                if inspect.isawaitable(after_result):
                    await after_result
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        return result

    async def emit_with_result(self, name: str, **payload: Any) -> tuple[Any, bool]:
        """Emit an event and get a result with blocked flag.

        Returns:
            (result, blocked) - result from hooks and whether it was blocked
        """
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")

        for fn in list(self._before_hooks.get(name, [])):
            try:
                result = fn(**payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        result = None
        blocked = False
        for fn in list(self._hooks[name]):
            try:
                result = fn(**payload)
                if inspect.isawaitable(result):
                    result = await result
                if result is not None and hasattr(result, "__blocked__"):
                    blocked = getattr(result, "__blocked__", False)
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        for fn in list(self._after_hooks.get(name, [])):
            try:
                after_result = fn(**payload)
                if inspect.isawaitable(after_result):
                    await after_result
            except Exception as exc:
                self.errors.append(exc)
                if self.fail_fast:
                    raise

        return result, blocked

    def clear(self) -> None:
        """Clear all registered hooks."""
        self._hooks = {name: [] for name in HOOK_NAMES}
        self._before_hooks = {name: [] for name in HOOK_NAMES}
        self._after_hooks = {name: [] for name in HOOK_NAMES}
        self.errors.clear()


class HookResult:
    """Result from a hook that can signal blocking."""
    __blocked__ = False

    def __init__(self, value: Any = None, blocked: bool = False) -> None:
        self.value = value
        self.__blocked__ = blocked


def block() -> HookResult:
    """Create a blocking hook result."""
    return HookResult(blocked=True)


def allow() -> HookResult:
    """Create an allowing hook result."""
    return HookResult(blocked=False)


global_hooks = HookRegistry()
