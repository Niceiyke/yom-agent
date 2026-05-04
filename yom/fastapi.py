"""FastAPI adapter for agent-core."""

from __future__ import annotations

from typing import Any, Callable, Literal

from yom import AgentRuntime, RuntimeSettings, build_runtime
from yom.models import RuntimeRunResult

try:
    from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
except ImportError:
    FastAPI = None
    APIRouter = None


class AgentRouter:
    """
    FastAPI router adapter for agent-core runtime.

    Provides REST and WebSocket endpoints for agent interaction.
    Can be included in an existing FastAPI app via `app.include_router(router)`.

    Usage:
        from yom.fastapi import create_agent_router

        router = create_agent_router(
            settings=RuntimeSettings(
                runtime_id="helpdesk",
                system_prompt="You are a helpdesk agent...",
            )
        )
        app.include_router(router)
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        prefix: str = "/agent",
        auth_hook: Callable[..., bool] | None = None,
    ):
        self.runtime = runtime
        self.prefix = prefix
        self.auth_hook = auth_hook

    def get_router(self) -> APIRouter:
        """Get the FastAPI router with all endpoints."""
        router = APIRouter(prefix=self.prefix)

        @router.get("/health")
        async def health():
            return {
                "status": "ok",
                "runtime_id": self.runtime.settings.runtime_id,
                "tools_count": len(self.runtime.list_tools()),
            }

        @router.get("/tools")
        async def list_tools():
            tools = []
            for tool in self.runtime.list_tools():
                name = getattr(tool, "name", None) or getattr(tool, "_tool_name", "unknown")
                desc = getattr(tool, "_tool_description", "") or getattr(tool, "description", "")
                tools.append({
                    "name": name,
                    "description": desc,
                })
            return {"tools": tools}

        @router.post("/{session_id}/start")
        async def start_session(session_id: str, body: dict[str, Any]):
            prompt = body.get("prompt", "")
            result: RuntimeRunResult = await self.runtime.run_prompt(
                prompt=prompt,
                session_id=session_id,
            )
            return result.to_dict()

        @router.get("/{session_id}/history")
        async def get_history(session_id: str):
            # Try to load from session backend
            deps = getattr(self.runtime, "_deps", None)
            session_backend = getattr(deps, "session_backend", None) if deps else None
            if session_backend:
                state = await session_backend.load(session_id)
                if state:
                    return {
                        "session_id": session_id,
                        "messages": [m.to_dict() for m in state.messages],
                        "current_turn": state.current_turn,
                    }
            return JSONResponse(
                status_code=404,
                content={"error": "Session not found"}
            )

        @router.get("/{session_id}/state")
        async def get_state(session_id: str):
            deps = getattr(self.runtime, "_deps", None)
            session_backend = getattr(deps, "session_backend", None) if deps else None
            if session_backend:
                state = await session_backend.load(session_id)
                if state:
                    return state.to_dict()
            return JSONResponse(
                status_code=404,
                content={"error": "Session not found"}
            )

        @router.delete("/{session_id}")
        async def delete_session(session_id: str):
            deps = getattr(self.runtime, "_deps", None)
            session_backend = getattr(deps, "session_backend", None) if deps else None
            if session_backend:
                await session_backend.delete(session_id)
                return {"status": "deleted", "session_id": session_id}
            return JSONResponse(
                status_code=404,
                content={"error": "Session backend not configured"}
            )

        @router.websocket("/{session_id}/ws")
        async def websocket_session(websocket: WebSocket, session_id: str):
            await websocket.accept()

            if self.auth_hook:
                try:
                    if not self.auth_hook(websocket):
                        await websocket.close(code=4001)
                        return
                except Exception:
                    await websocket.close(code=4001)
                    return

            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "prompt":
                        prompt = data.get("prompt", "")
                        result: RuntimeRunResult = await self.runtime.run_prompt(
                            prompt=prompt,
                            session_id=session_id,
                        )
                        await websocket.send_json({
                            "type": "response",
                            **result.to_dict()
                        })

                    elif msg_type == "abort":
                        await websocket.send_json({"type": "aborted"})

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                pass
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })

        return router


def create_agent_router(
    settings: RuntimeSettings,
    auth_hook: Callable[..., bool] | None = None,
    prefix: str = "/agent",
    mode: Literal["standalone", "yom_agent"] = "standalone",
) -> AgentRouter:
    """
    Create an AgentRouter with runtime built from settings.

    This is the main entry point for FastAPI integration:

        from yom.fastapi import create_agent_router

        router = create_agent_router(
            settings=RuntimeSettings(
                runtime_id="helpdesk",
                system_prompt="You are a helpdesk agent...",
            )
        )
        app.include_router(router.get_router())

    Args:
        settings: RuntimeSettings configuration
        auth_hook: Optional auth callback (receives WebSocket or Request)
        prefix: URL prefix for agent endpoints
        mode: "standalone" or "yom_agent"
    """
    runtime = build_runtime(settings, mode=mode)
    return AgentRouter(runtime=runtime, prefix=prefix, auth_hook=auth_hook)


def create_agent_app(
    settings: RuntimeSettings,
    title: str | None = None,
    auth_hook: Callable[..., bool] | None = None,
    prefix: str = "/agent",
    mode: Literal["standalone", "yom_agent"] = "standalone",
) -> FastAPI:
    """
    Create a standalone FastAPI app with agent endpoints.

    This creates a complete FastAPI application:

        from yom.fastapi import create_agent_app

        app = create_agent_app(
            settings=RuntimeSettings(
                runtime_id="helpdesk",
                system_prompt="You are a helpdesk agent...",
            )
        )
        # Run with: uvicorn.run(app, host="0.0.0.0", port=8000)

    Args:
        settings: RuntimeSettings configuration
        title: Optional FastAPI app title (defaults to runtime_id)
        auth_hook: Optional auth callback
        prefix: URL prefix for agent endpoints
        mode: "standalone" or "yom_agent"
    """
    if FastAPI is None:
        raise ImportError("fastapi not installed. Run: pip install agent-core[fastapi]")

    runtime = build_runtime(settings, mode=mode)
    router = AgentRouter(runtime=runtime, prefix=prefix, auth_hook=auth_hook)

    app = FastAPI(
        title=title or f"Agent: {settings.runtime_id}",
        description="agent-core powered agent endpoint",
    )

    app.include_router(router.get_router())

    @app.get("/")
    async def root():
        return {
            "message": "agent-core FastAPI endpoint",
            "agent_endpoint": f"{prefix}/health",
            "runtime_id": settings.runtime_id,
        }

    return app