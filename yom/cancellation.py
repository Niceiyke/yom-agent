"""Cancellation token for aborting long-running operations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class CancellationToken:
    """Token for cancelling long-running operations.
    
    Usage:
        token = CancellationToken()
        
        # Pass to agent
        await agent.run("task", cancellation_token=token)
        
        # Cancel from another task
        token.cancel()
        
        # Or cancel after timeout
        asyncio.create_task(token.cancel_after(30))
        
        # Check if cancelled
        if token.is_cancelled:
            print("Operation was cancelled")
    """
    _cancelled: bool = field(default=False, repr=False)
    _cancel_reason: str | None = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
    
    @property
    def cancel_reason(self) -> str | None:
        """Get the reason for cancellation if set."""
        return self._cancel_reason
    
    def cancel(self, reason: str | None = None) -> None:
        """Request cancellation.
        
        Args:
            reason: Optional reason for cancellation
        """
        self._cancelled = True
        self._cancel_reason = reason or "Cancelled by user"
    
    async def cancel_async(self, reason: str | None = None) -> None:
        """Request cancellation asynchronously."""
        async with self._lock:
            self.cancel(reason)
    
    async def cancel_after(self, seconds: float) -> None:
        """Cancel after a delay.
        
        Args:
            seconds: Number of seconds to wait before cancelling
        """
        await asyncio.sleep(seconds)
        await self.cancel_async(f"Cancelled after {seconds} seconds")
    
    def reset(self) -> None:
        """Reset the cancellation token to allow reuse."""
        self._cancelled = False
        self._cancel_reason = None
    
    def throw_if_cancelled(self) -> None:
        """Raise CancelledError if cancellation was requested."""
        if self._cancelled:
            raise asyncio.CancelledError(self._cancel_reason)
    
    async def throw_if_cancelled_async(self) -> None:
        """Raise CancelledError if cancellation was requested (async version)."""
        if self._cancelled:
            raise asyncio.CancelledError(self._cancel_reason)
    
    def __await__(self):
        """Allow `await token` pattern for waiting until cancelled."""
        async def _wait():
            while not self._cancelled:
                await asyncio.sleep(0.1)
        return _wait().__await__()


class CancellationScope:
    """Scope that automatically cancels on exit.
    
    Usage:
        async with CancellationScope() as scope:
            # Pass scope.token to operations
            await agent.run("task", cancellation_token=scope.token)
            
        # Automatically cancelled when exiting scope
    """
    
    def __init__(self, cancel_on_exit: bool = False):
        self.token = CancellationToken()
        self._cancel_on_exit = cancel_on_exit
        self._on_cancel: list[Callable[[], Awaitable[None]]] = []
    
    async def __aenter__(self) -> CancellationScope:
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._cancel_on_exit and not self.token.is_cancelled:
            self.token.cancel("Scope exited")
        # Note: Don't raise CancelledError here - let it propagate naturally
    
    def on_cancel(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register a callback to run when cancelled."""
        self._on_cancel.append(callback)


# Global cancellation registry for Agent.abort()
_global_abort_tokens: dict[int, CancellationToken] = {}


def _register_abort_token(agent_id: int, token: CancellationToken) -> None:
    """Register a token for an agent (internal use)."""
    _global_abort_tokens[agent_id] = token


def _unregister_abort_token(agent_id: int) -> None:
    """Unregister a token for an agent (internal use)."""
    _global_abort_tokens.pop(agent_id, None)


def _get_abort_token(agent_id: int) -> CancellationToken | None:
    """Get the abort token for an agent (internal use)."""
    return _global_abort_tokens.get(agent_id)
