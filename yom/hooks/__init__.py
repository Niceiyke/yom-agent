"""Hooks system for runtime event observability."""

from yom.hooks.hooks import (
    HOOK_NAMES,
    HookRegistry,
    HookResult,
    block,
    allow,
    global_hooks,
)

__all__ = [
    "HOOK_NAMES",
    "HookRegistry",
    "HookResult",
    "block",
    "allow",
    "global_hooks",
]
