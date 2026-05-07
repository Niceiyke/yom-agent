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

    def unregister(self, name: str, fn: HookFn) -> bool:
        """Unregister a specific hook function.
        
        Args:
            name: Event name
            fn: The hook function to remove
            
        Returns:
            True if the hook was found and removed, False otherwise.
        
        Example:
            async def my_hook(state):
                print("called")
            
            hooks.register("before_turn", my_hook)
            hooks.unregister("before_turn", my_hook)  # Removes it
        """
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")
        
        removed = False
        
        # Check main hooks
        if fn in self._hooks[name]:
            self._hooks[name].remove(fn)
            removed = True
        
        # Check before hooks
        if fn in self._before_hooks.get(name, []):
            self._before_hooks[name].remove(fn)
            removed = True
        
        # Check after hooks
        if fn in self._after_hooks.get(name, []):
            self._after_hooks[name].remove(fn)
            removed = True
        
        return removed

    def unregister_all(self, name: str | None = None) -> int:
        """Unregister all hooks, or all hooks for a specific event.
        
        Args:
            name: Optional event name. If None, clears all hooks.
            
        Returns:
            Number of hooks removed.
        """
        if name is not None:
            if name not in HOOK_NAMES:
                raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")
            count = (
                len(self._hooks.get(name, [])) +
                len(self._before_hooks.get(name, [])) +
                len(self._after_hooks.get(name, []))
            )
            self._hooks[name] = []
            self._before_hooks[name] = []
            self._after_hooks[name] = []
            return count
        else:
            count = 0
            for n in HOOK_NAMES:
                count += len(self._hooks.get(n, []))
                count += len(self._before_hooks.get(n, []))
                count += len(self._after_hooks.get(n, []))
            self.clear()
            return count

    def has_hook(self, name: str, fn: HookFn) -> bool:
        """Check if a hook function is registered.
        
        Args:
            name: Event name
            fn: Hook function to check
            
        Returns:
            True if the hook is registered, False otherwise.
        """
        if name not in HOOK_NAMES:
            return False
        return (
            fn in self._hooks.get(name, []) or
            fn in self._before_hooks.get(name, []) or
            fn in self._after_hooks.get(name, [])
        )

    def get_hooks(self, name: str) -> dict[str, list[HookFn]]:
        """Get all hooks registered for an event.
        
        Args:
            name: Event name
            
        Returns:
            Dict with 'before', 'main', and 'after' keys mapping to lists of hooks.
        """
        if name not in HOOK_NAMES:
            raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")
        return {
            "before": list(self._before_hooks.get(name, [])),
            "main": list(self._hooks.get(name, [])),
            "after": list(self._after_hooks.get(name, [])),
        }

    def count(self, name: str | None = None) -> int:
        """Count registered hooks.
        
        Args:
            name: Optional event name. If None, counts all hooks.
            
        Returns:
            Number of registered hooks.
        """
        if name is not None:
            if name not in HOOK_NAMES:
                raise ValueError(f"Unknown hook: {name}. Must be one of: {sorted(HOOK_NAMES)}")
            return (
                len(self._hooks.get(name, [])) +
                len(self._before_hooks.get(name, [])) +
                len(self._after_hooks.get(name, []))
            )
        else:
            total = 0
            for n in HOOK_NAMES:
                total += self.count(n)
            return total

    def list_events(self) -> list[str]:
        """List all event names that have registered hooks.
        
        Returns:
            List of event names with at least one hook registered.
        """
        events = []
        for name in HOOK_NAMES:
            if self.count(name) > 0:
                events.append(name)
        return events

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
