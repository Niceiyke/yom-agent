"""Telegram Bot with Multi-Session Support"""

import asyncio
import os
from pathlib import Path
from yom import Agent
from yom.toolsets.telegram import TelegramBot


async def main():
    """Multi-session Telegram bot example."""
    
    # Create session storage directory
    storage_dir = Path("./telegram_sessions")
    storage_dir.mkdir(exist_ok=True)
    
    # Create agent with your tools
    agent = Agent(
        tools=["core", "http_request", "s3_put", "s3_get"],
        system_prompt="You are a helpful AI assistant. Be concise.",
    )
    
    # Create bot with multi-session support
    bot = TelegramBot(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        agent=agent,
        storage_dir=storage_dir,  # Persist sessions to disk
        session_timeout=30 * 86400,  # 30 days
        allowed_users=[],  # Empty = allow everyone, or add specific user IDs
    )
    
    # Optional: Set custom agent for specific users
    # dev_agent = Agent(tools=["core", "shell", "github_api"])
    # bot.set_user_agent(user_id=123456789, agent=dev_agent)
    
    print("🤖 Multi-session Telegram bot started!")
    print("📁 Sessions will be saved to ./telegram_sessions/")
    print("Press Ctrl+C to stop.")
    
    try:
        await bot.poll()
    except KeyboardInterrupt:
        bot.stop()
        # Save all sessions before exit
        await bot._session_manager.save_all_sessions()
        print("\n👋 Bot stopped. Sessions saved.")


if __name__ == "__main__":
    asyncio.run(main())
