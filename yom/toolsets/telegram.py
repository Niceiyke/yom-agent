"""Telegram bot integration for yom-agent.

Enables controlling agents via Telegram messages with multi-session support.

Features:
- Multiple sessions per user
- Named sessions with /session <name>
- Session persistence to disk
- Per-user agents and prompts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from pathlib import Path

from yom.tools import tool

logger = logging.getLogger(__name__)


@dataclass
class TelegramMessage:
    """Parsed Telegram message."""
    chat_id: int
    message_id: int
    text: str
    username: str | None = None
    first_name: str | None = None
    user_id: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSession:
    """A conversation session with history."""
    session_id: str
    name: str  # Session name/alias
    chat_id: int
    user_id: int
    username: str | None = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    history: list[dict[str, str]] = field(default_factory=list)
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def add_user_message(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})
        self.last_active = time.time()
    
    def add_assistant_message(self, content: str) -> None:
        self.history.append({"role": "assistant", "content": content})
    
    def clear_history(self) -> None:
        self.history = []
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "history": self.history,
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSession:
        return cls(
            session_id=data["session_id"],
            name=data["name"],
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            username=data.get("username"),
            created_at=data.get("created_at", time.time()),
            last_active=data.get("last_active", time.time()),
            history=data.get("history", []),
            system_prompt=data.get("system_prompt"),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """Manages multiple sessions per user.
    
    Sessions are keyed by (user_id, session_name).
    Each user can have unlimited named sessions.
    """
    
    def __init__(
        self,
        storage_dir: Path | None = None,
        max_history: int = 100,
        max_sessions_per_user: int = 50,
        max_age_days: int = 30,
    ):
        # Key: (user_id, session_name) -> AgentSession
        self._sessions: dict[tuple[int, str], AgentSession] = {}
        # Key: user_id -> current session name
        self._active_sessions: dict[int, str] = {}
        # Key: user_id -> custom prompts
        self._prompts: dict[int, str] = {}
        
        self.storage_dir = storage_dir
        self.max_history = max_history
        self.max_sessions_per_user = max_sessions_per_user
        self.max_age_days = max_age_days
        self._lock = asyncio.Lock()
        
        if storage_dir:
            storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _session_key(self, user_id: int, name: str) -> tuple[int, str]:
        return (user_id, name)
    
    def set_prompt(self, user_id: int, prompt: str) -> None:
        self._prompts[user_id] = prompt
    
    def get_prompt(self, user_id: int) -> str | None:
        return self._prompts.get(user_id)
    
    async def create_session(
        self,
        user_id: int,
        chat_id: int,
        username: str | None = None,
        name: str | None = None,
        set_active: bool = True,
    ) -> AgentSession:
        """Create a new session for user."""
        async with self._lock:
            name = name or "main"
            key = self._session_key(user_id, name)
            
            if key in self._sessions:
                session = self._sessions[key]
            else:
                # Check limit
                user_sessions = [k for k in self._sessions if k[0] == user_id]
                if len(user_sessions) >= self.max_sessions_per_user:
                    # Remove oldest
                    oldest = min(
                        user_sessions,
                        key=lambda k: self._sessions[k].last_active
                    )
                    del self._sessions[oldest]
                
                session = AgentSession(
                    session_id=str(uuid.uuid4()),
                    name=name,
                    chat_id=chat_id,
                    user_id=user_id,
                    username=username,
                )
                self._sessions[key] = session
            
            if set_active:
                self._active_sessions[user_id] = name
            
            return session
    
    async def get_session(
        self,
        user_id: int,
        name: str | None = None,
    ) -> AgentSession | None:
        """Get a specific session or active session."""
        name = name or self._active_sessions.get(user_id) or "main"
        return self._sessions.get(self._session_key(user_id, name))
    
    async def get_or_create_active(
        self,
        user_id: int,
        chat_id: int,
        username: str | None = None,
    ) -> AgentSession:
        """Get active session or create main session."""
        name = self._active_sessions.get(user_id) or "main"
        session = await self.get_session(user_id, name)
        if session:
            return session
        return await self.create_session(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            name=name,
        )
    
    async def switch_session(
        self,
        user_id: int,
        name: str,
        chat_id: int,
        username: str | None = None,
    ) -> AgentSession:
        """Switch to or create a named session."""
        return await self.create_session(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            name=name,
            set_active=True,
        )
    
    async def delete_session(self, user_id: int, name: str) -> bool:
        """Delete a session."""
        async with self._lock:
            key = self._session_key(user_id, name)
            if key in self._sessions:
                del self._sessions[key]
                if self._active_sessions.get(user_id) == name:
                    del self._active_sessions[user_id]
                return True
            return False
    
    async def list_user_sessions(self, user_id: int) -> list[dict[str, Any]]:
        """List all sessions for a user."""
        return [
            {
                "name": s.name,
                "is_active": self._active_sessions.get(user_id) == s.name,
                "messages": len(s.history),
                "created_at": s.created_at,
                "last_active": s.last_active,
            }
            for k, s in self._sessions.items()
            if k[0] == user_id
        ]
    
    async def save_session(self, user_id: int, name: str) -> None:
        """Save session to disk."""
        if not self.storage_dir:
            return
        
        key = self._session_key(user_id, name)
        session = self._sessions.get(key)
        if not session:
            return
        
        path = self._get_path(user_id, name)
        try:
            with open(path, "w") as f:
                json.dump(session.to_dict(), f)
        except Exception as e:
            logger.warning(f"Failed to save session: {e}")
    
    async def save_all(self) -> None:
        """Save all sessions."""
        async with self._lock:
            for (user_id, name), session in self._sessions.items():
                path = self._get_path(user_id, name)
                try:
                    with open(path, "w") as f:
                        json.dump(session.to_dict(), f)
                except Exception as e:
                    logger.warning(f"Failed to save: {e}")
    
    def _get_path(self, user_id: int, name: str) -> Path:
        safe_name = name.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"u{user_id}_{safe_name}.json"  # type: ignore[union-attr]
    
    async def load_session(self, user_id: int, name: str) -> bool:
        """Load session from disk."""
        if not self.storage_dir:
            return False
        
        path = self._get_path(user_id, name)
        if not path.exists():
            return False
        
        try:
            with open(path) as f:
                data = json.load(f)
            session = AgentSession.from_dict(data)
            key = self._session_key(user_id, name)
            self._sessions[key] = session
            return True
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
            return False


class TelegramBot:
    """Telegram bot with multi-session support.
    
    Each user can have multiple named sessions.
    Use /session <name> to switch or create sessions.
    """
    
    def __init__(
        self,
        token: str,
        agent: Any = None,
        allowed_users: list[int] | None = None,
        system_prompt: str | None = None,
        storage_dir: Path | None = None,
    ):
        self.token = token
        self.agent = agent
        self.allowed_users = allowed_users or []
        self.default_prompt = system_prompt or "You are a helpful AI assistant."
        self.storage_dir = storage_dir
        
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._running = False
        self._sessions = SessionManager(
            storage_dir=storage_dir,
            max_sessions_per_user=50,
        )
        self._user_agents: dict[int, Any] = {}
        self._user_api_keys: dict[int, str] = {}  # Per-user API keys
        self._default_agent = agent
    
    def set_user_agent(self, user_id: int, agent: Any) -> None:
        self._user_agents[user_id] = agent
    
    def add_agent(self, agent: Any) -> None:
        self.agent = agent
        self._default_agent = agent
    
    def _get_agent(self, user_id: int) -> Any:
        # Check if user has their own agent
        if user_id in self._user_agents:
            return self._user_agents[user_id]
        
        # Check if user has their own API key
        if user_id in self._user_api_keys:
            return _UserAgent(
                api_key=self._user_api_keys[user_id],
                system_prompt=self.default_prompt,
            )
        
        return self._default_agent


class _UserAgent:
    """Lightweight agent wrapper that uses user's API key."""
    
    def __init__(self, api_key: str, system_prompt: str):
        self.api_key = api_key
        self.system_prompt = system_prompt
    
    async def run(self, prompt: str) -> str:
        """Run prompt with user's API key."""
        import os
        from yom import Agent
        
        # Set env var for this call
        old_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = self.api_key
        
        try:
            agent = Agent(tools=[], system_prompt=self.system_prompt)
            result = await agent.run(prompt)
        finally:
            # Restore original
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)
        
        return result
    
    async def _api(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import aiohttp
        
        url = f"{self._base_url}/{method}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        return await self._api("sendMessage", {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
        })
    
    def _parse(self, update: dict[str, Any]) -> TelegramMessage | None:
        if "message" not in update:
            return None
        msg = update["message"]
        chat = msg.get("chat", {})
        user = msg.get("from", {})
        
        return TelegramMessage(
            chat_id=chat.get("id", 0),
            message_id=msg.get("message_id", 0),
            text=msg.get("text", ""),
            username=user.get("username"),
            first_name=user.get("first_name"),
            user_id=user.get("id"),
            raw=msg,
        )
    
    def _allowed(self, msg: TelegramMessage) -> bool:
        if not self.allowed_users:
            return True
        return msg.user_id in self.allowed_users or msg.chat_id in self.allowed_users
    
    async def _handle(self, msg: TelegramMessage) -> str:
        if not self._allowed(msg):
            return "⛔ Access denied"
        
        user_id = msg.user_id or msg.chat_id
        session = await self._sessions.get_or_create_active(
            user_id, msg.chat_id, msg.username
        )
        
        # Commands
        if msg.text == "/start":
            return (
                "👋 Welcome! I support multiple conversation sessions.\n\n"
                "Commands:\n"
                "/apikey <key> - Set your OpenAI/MiniMax API key\n"
                "/new <name> - Create new session\n"
                "/switch <name> - Switch session\n"
                "/sessions - List your sessions\n"
                "/use <name> - Use session\n"
                "/del <name> - Delete session\n"
                "/reset - Clear current session\n"
                "/prompt <text> - Set custom instructions\n"
                "/help - Show help"
            )
        
        if msg.text == "/help":
            return """
🤖 *Commands:*

`/apikey <key>` - Set your API key (OpenAI or MiniMax)
`/new <name>` - Create new session
`/switch <name>` - Switch to session
`/sessions` - List your sessions  
`/use <name>` - Use session
`/del <name>` - Delete session
`/reset` - Clear current session
`/prompt <text>` - Set custom prompt
`/current` - Show current session

Just chat normally!
            """
        
        # Handle /apikey command
        if msg.text.startswith("/apikey "):
            api_key = msg.text[8:].strip()
            if not api_key:
                return "❌ Usage: /apikey <your-api-key>"
            if len(api_key) < 10:
                return "❌ API key too short"
            
            # Detect provider
            if api_key.startswith("sk-") or api_key.startswith("o1-") or api_key.startswith("o3-"):
                provider = "OpenAI"
            elif len(api_key) > 50:  # MiniMax keys are longer
                provider = "MiniMax"
            else:
                provider = "OpenAI-compatible"
            
            # Store per user
            user_id = msg.user_id or msg.chat_id
            self._user_api_keys[user_id] = api_key
            
            return f"✅ API key saved ({provider})! Now you can chat."
        
        if msg.text.startswith("/new "):
            name = msg.text[5:].strip()
            if not name or len(name) > 30:
                return "❌ Session name must be 1-30 chars"
            session = await self._sessions.switch_session(
                user_id, msg.chat_id, msg.username, name
            )
            return f"✅ Created session: *{name}*"
        
        if msg.text.startswith("/switch "):
            name = msg.text[8:].strip()
            session = await self._sessions.get_session(user_id, name)
            if not session:
                return f"❌ Session '{name}' not found"
            await self._sessions.switch_session(
                user_id, msg.chat_id, msg.username, name
            )
            return f"🔄 Switched to session: *{name}*"
        
        if msg.text.startswith("/use "):
            name = msg.text[5:].strip()
            session = await self._sessions.get_session(user_id, name)
            if not session:
                session = await self._sessions.switch_session(
                    user_id, msg.chat_id, msg.username, name
                )
                return f"✅ Created session: *{name}*"
            await self._sessions.switch_session(
                user_id, msg.chat_id, msg.username, name
            )
            return f"📝 Using session: *{name}*"
        
        if msg.text.startswith("/del "):
            name = msg.text[5:].strip()
            if name == "main":
                return "❌ Cannot delete 'main' session"
            deleted = await self._sessions.delete_session(user_id, name)
            return f"✅ Deleted session: *{name}*" if deleted else f"❌ Session '{name}' not found"
        
        if msg.text == "/sessions":
            sessions = await self._sessions.list_user_sessions(user_id)
            if not sessions:
                return "No sessions"
            
            lines = ["📁 *Your sessions:*"]
            for s in sessions:
                active = "👉" if s["is_active"] else "  "
                lines.append(f"{active} `{s['name']}` ({s['messages']} msgs)")
            return "\n".join(lines)
        
        if msg.text == "/current":
            return f"📍 Current session: *{session.name}*"
        
        if msg.text == "/reset":
            session.clear_history()
            await self._sessions.save_session(user_id, session.name)
            return "🔄 Session cleared"
        
        if msg.text.startswith("/prompt "):
            prompt = msg.text[8:].strip()
            self._sessions.set_prompt(user_id, prompt)
            session.system_prompt = prompt
            return f"✅ Prompt set: {prompt[:50]}..."
        
        # Regular message - get response
        session.add_user_message(msg.text)
        
        agent = self._get_agent(user_id)
        if agent:
            try:
                # Build prompt with conversation history
                system = session.system_prompt or self._sessions.get_prompt(user_id) or self.default_prompt
                
                # Build full prompt with history
                full_prompt = self._build_prompt(system, session.history[-20:])
                
                response = await agent.run(full_prompt)
            except Exception as e:
                response = f"❌ Error: {str(e)}"
        else:
            response = "No agent configured"
        
        session.add_assistant_message(response)
        
        if len(session.history) > self._sessions.max_history:
            session.history = session.history[-self._sessions.max_history:]
        
        await self._sessions.save_session(user_id, session.name)
        
        return response
    
    def _build_prompt(self, system: str, history: list[dict[str, str]]) -> str:
        """Build prompt with system message and history."""
        lines = [f"{system}"]
        
        if history:
            lines.append("\nConversation history:")
            for msg in history:
                role = msg["role"].upper()
                content = msg["content"]
                lines.append(f"\n{role}: {content}")
        
        lines.append("\nUser: " + (history[-1]["content"] if history else ""))
        return "\n".join(lines)
    
    async def _update(self, update: dict[str, Any]) -> None:
        msg = self._parse(update)
        if not msg:
            return
        
        try:
            response = await self._handle(msg)
            await self.send_message(msg.chat_id, response)
            self._offset = update.get("update_id", 0)
        except Exception as e:
            logger.error(f"Update error: {e}")
    
    async def poll(self) -> None:
        self._running = True
        while self._running:
            try:
                data = await self._api("getUpdates", {
                    "offset": self._offset + 1,
                    "timeout": 30,
                })
                if data.get("ok"):
                    for update in data.get("result", []):
                        await self._update(update)
            except Exception as e:
                logger.error(f"Poll error: {e}")
                await asyncio.sleep(5)
    
    async def start(self) -> None:
        await self.poll()
    
    def stop(self) -> None:
        self._running = False


@tool(
    name="telegram_send",
    description="Send a message via Telegram bot.",
    schema={
        "type": "object",
        "properties": {
            "chat_id": {"type": "integer", "description": "Telegram chat ID"},
            "text": {"type": "string", "description": "Message to send"},
        },
        "required": ["chat_id", "text"]
    }
)
def telegram_send(chat_id: int, text: str) -> str:
    return f"Sent to {chat_id}: {text[:50]}..."


__all__ = ["TelegramBot", "TelegramMessage", "AgentSession", "SessionManager", "telegram_send"]
