"""
Telegram Bot Setup for yom-agent

This example shows how to deploy yom-agent as a Telegram bot.

SETUP STEPS:
1. Create a bot via @BotFather on Telegram
2. Get your bot token
3. (Optional) Set up webhook or use polling
4. Run the bot
"""

import asyncio
import os
from yom import Agent
from yom.toolsets.telegram import TelegramBot


# =============================================================================
# OPTION 1: Simple Polling (easy, for small scale)
# =============================================================================

async def run_with_polling():
    """Run bot with long polling - simplest setup."""
    agent = Agent(
        tools=["core"],
        system_prompt="You are a helpful AI assistant. Be concise but thorough.",
    )
    
    bot = TelegramBot(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        agent=agent,
        # allowed_users=[123456789],  # Uncomment to restrict access
    )
    
    print("🤖 Bot started! Send a message to your Telegram bot.")
    print("Press Ctrl+C to stop.")
    
    try:
        await bot.poll()
    except KeyboardInterrupt:
        bot.stop()
        print("\n👋 Bot stopped.")


# =============================================================================
# OPTION 2: Webhook with FastAPI (recommended for production)
# =============================================================================

async def run_with_webhook():
    """Run bot with webhook - production ready."""
    from fastapi import FastAPI, Request, HTTPException
    from contextlib import asynccontextmanager
    
    from yom.toolsets.telegram import TelegramBot
    
    # Create agent
    agent = Agent(
        tools=["core"],
        system_prompt="You are a helpful AI assistant.",
    )
    
    # Create bot
    bot = TelegramBot(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        agent=agent,
    )
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Set webhook on startup
        webhook_url = os.environ["WEBHOOK_URL"]
        secret = os.environ.get("WEBHOOK_SECRET", "")
        
        await bot._make_request(
            "setWebhook",
            {"url": webhook_url, "secret_token": secret}
        )
        print(f"✅ Webhook set to {webhook_url}")
        
        yield
        
        # Cleanup
        await bot._make_request("deleteWebhook")
    
    app = FastAPI(lifespan=lifespan)
    
    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request):
        secret = os.environ.get("WEBHOOK_SECRET", "")
        
        # Verify secret if set
        if secret:
            signature = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            body = await request.body()
            if not bot.verify_webhook(body, signature, secret):
                raise HTTPException(403, "Forbidden")
        
        update = await request.json()
        await bot.handle_webhook(update)
        return {"ok": True}
    
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    return app


# =============================================================================
# OPTION 3: Webhook with Starlette (lighter alternative)
# =============================================================================

def run_with_starlette():
    """Run with Starlette (no FastAPI dependency)."""
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    import uvicorn
    
    from yom.toolsets.telegram import TelegramBot
    
    agent = Agent(tools=["core"])
    
    bot = TelegramBot(
        token=os.environ["TELEGRAM_BOT_TOKEN"],
        agent=agent,
    )
    
    async def webhook(request: Request):
        update = await request.json()
        await bot.handle_webhook(update)
        return JSONResponse({"ok": True})
    
    async def startup():
        webhook_url = os.environ["WEBHOOK_URL"]
        await bot._make_request("setWebhook", {"url": webhook_url})
        print(f"✅ Webhook set")
    
    app = Starlette(
        routes=[Route("/telegram/webhook", webhook, methods=["POST"])],
        on_startup=[startup],
    )
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


# =============================================================================
# OPTION 4: Docker deployment
# =============================================================================

def generate_dockerfile():
    """Generate Dockerfile for Telegram bot."""
    return '''FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[telegram]"

# Copy application
COPY bot.py .

# Run
CMD ["python", "bot.py"]
'''


def generate_docker_compose():
    """Generate docker-compose.yml for Telegram bot."""
    return '''version: "3.8"

services:
  telegram-bot:
    build: .
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - WEBHOOK_URL=https://yourdomain.com/telegram/webhook
      - WEBHOOK_SECRET=${WEBHOOK_SECRET:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    restart: unless-stopped
'''


def generate_bot_py():
    """Generate the bot.py file."""
    return '''#!/usr/bin/env python3
"""Telegram bot entrypoint for yom-agent."""

import asyncio
import os
from yom import Agent
from yom.toolsets.telegram import TelegramBot


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable required")
    
    # Create agent with your preferred tools
    agent = Agent(
        tools=["core", "http_request", "s3_put", "s3_get"],
        system_prompt=os.environ.get("SYSTEM_PROMPT", "You are a helpful AI assistant."),
    )
    
    # Create bot
    bot = TelegramBot(
        token=token,
        agent=agent,
        allowed_users=parse_allowed_users(),
    )
    
    # Run
    asyncio.run(bot.poll())


def parse_allowed_users():
    """Parse ALLOWED_USERS from env (comma-separated IDs)."""
    users = os.environ.get("ALLOWED_USERS", "")
    if not users:
        return []
    return [int(uid.strip()) for uid in users.split(",") if uid.strip()]


if __name__ == "__main__":
    main()
'''


# =============================================================================
# QUICK START
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
📱 yom Telegram Bot Setup

Usage: python telegram_bot.py [mode]

Modes:
  polling    - Long polling (simple, for testing)
  webhook   - Webhook with FastAPI (production)
  starlette - Webhook with Starlette (lightweight)
  generate  - Generate deployment files

Environment Variables Required:
  TELEGRAM_BOT_TOKEN  - Get from @BotFather

Environment Variables Optional:
  WEBHOOK_URL        - Your public URL for webhooks
  WEBHOOK_SECRET     - Secret for webhook verification
  ALLOWED_USERS      - Comma-separated Telegram user IDs
  OPENAI_API_KEY     - For AI responses
  SYSTEM_PROMPT      - Custom system prompt

Examples:
  # Polling (simple)
  TELEGRAM_BOT_TOKEN=123:abc python telegram_bot.py polling

  # Webhook with FastAPI  
  TELEGRAM_BOT_TOKEN=123:abc WEBHOOK_URL=https://bot.example.com/telegram/webhook python telegram_bot.py webhook

  # Generate deployment files
  python telegram_bot.py generate
        """)
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "polling":
        asyncio.run(run_with_polling())
    elif mode == "webhook":
        import uvicorn
        app = asyncio.run(run_with_webhook())
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif mode == "starlette":
        run_with_starlette()
    elif mode == "generate":
        with open("Dockerfile", "w") as f:
            f.write(generate_dockerfile())
        with open("docker-compose.yml", "w") as f:
            f.write(generate_docker_compose())
        with open("bot.py", "w") as f:
            f.write(generate_bot_py())
        print("✅ Generated: Dockerfile, docker-compose.yml, bot.py")
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
