"""Hook registry utilities."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

Hook = Callable[..., Awaitable[Any] | Any]


@dataclass
class HookResult:
    value: Any = None
    blocked: bool = False

    @property
    def __blocked__(self) -> bool:
        return self.blocked


def block(value: Any = None) -> HookResult:
    return HookResult(value=value, blocked=True)


def allow(value: Any = None) -> HookResult:
    return HookResult(value=value, blocked=False)


class HookRegistry:
    VALID_EVENTS = {
        "agent_start",
        "agent_end",
        "before_turn",
        "after_turn",
        "before_tool_call",
        "after_tool_call",
    }

    def __init__(self, fail_fast: bool = False):
        self.fail_fast = fail_fast
        self.errors: list[Exception] = []
        self._hooks: dict[str, list[Hook]] = {e: [] for e in self.VALID_EVENTS}
        self._before_hooks: dict[str, list[Hook]] = {e: [] for e in self.VALID_EVENTS}
        self._after_hooks: dict[str, list[Hook]] = {e: [] for e in self.VALID_EVENTS}

    def _ensure_event(self, event: str) -> None:
        if event not in self.VALID_EVENTS:
            raise ValueError(f"Unknown hook: {event}")

    def on(self, event: str, fn: Hook | None = None):
        self._ensure_event(event)
        if fn is not None:
            self._hooks[event].append(fn)
            return fn

        def decorator(func: Hook):
            self._hooks[event].append(func)
            return func

        return decorator

    def register(self, event: str, fn: Hook) -> None:
        self.on(event, fn)

    def before(self, event: str, fn: Hook) -> None:
        self._ensure_event(event)
        self._before_hooks[event].append(fn)

    def after(self, event: str, fn: Hook) -> None:
        self._ensure_event(event)
        self._after_hooks[event].append(fn)

    async def _run(self, fn: Hook, **kwargs):
        result = fn(**kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return result

    async def emit(self, event: str, **kwargs):
        self._ensure_event(event)
        last = None
        handlers = [
            *list(self._before_hooks[event]),
            *list(self._hooks[event]),
            *list(self._after_hooks[event]),
        ]
        for fn in handlers:
            try:
                last = await self._run(fn, **kwargs)
            except Exception as e:
                self.errors.append(e)
                if self.fail_fast:
                    raise
        return last

    async def emit_with_result(self, event: str, **kwargs):
        result = await self.emit(event, **kwargs)
        if isinstance(result, HookResult):
            return result, result.__blocked__
        return HookResult(value=result, blocked=False), False

    @property
    def before_turn(self):
        return self.on("before_turn")

    @property
    def after_turn(self):
        return self.on("after_turn")

    def unregister(self, event: str, fn: Hook) -> bool:
        self._ensure_event(event)
        removed = False
        for bucket in (self._before_hooks[event], self._hooks[event], self._after_hooks[event]):
            if fn in bucket:
                bucket.remove(fn)
                removed = True
        return removed

    def unregister_all(self, event: str | None = None) -> int:
        if event is not None:
            self._ensure_event(event)
            count = len(self._before_hooks[event]) + len(self._hooks[event]) + len(self._after_hooks[event])
            self._before_hooks[event].clear()
            self._hooks[event].clear()
            self._after_hooks[event].clear()
            return count

        total = self.count()
        self.clear()
        return total

    def clear(self) -> None:
        for e in self.VALID_EVENTS:
            self._before_hooks[e].clear()
            self._hooks[e].clear()
            self._after_hooks[e].clear()

    def has_hook(self, event: str, fn: Hook) -> bool:
        self._ensure_event(event)
        return fn in self._before_hooks[event] or fn in self._hooks[event] or fn in self._after_hooks[event]

    def get_hooks(self, event: str) -> dict[str, list[Hook]]:
        self._ensure_event(event)
        return {
            "before": list(self._before_hooks[event]),
            "main": list(self._hooks[event]),
            "after": list(self._after_hooks[event]),
        }

    def count(self, event: str | None = None) -> int:
        if event is not None:
            self._ensure_event(event)
            return len(self._before_hooks[event]) + len(self._hooks[event]) + len(self._after_hooks[event])
        return sum(self.count(e) for e in self.VALID_EVENTS)

    def list_events(self) -> list[str]:
        return [e for e in self.VALID_EVENTS if self.count(e) > 0]


global_hooks = HookRegistry()

__all__ = ["HookRegistry", "HookResult", "allow", "block", "global_hooks"]
