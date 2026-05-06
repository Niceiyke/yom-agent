# Telegram Bot Setup Guide

Deploy your yom-agent as a Telegram bot in minutes.

## 🚀 Quick Start

### 1. Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts to name your bot
4. Copy the **bot token** (format: `123456:ABC-DEF...`)

### 2. Install yom with Telegram support

```bash
pip install yom[telegram]
```

### 3. Run the Bot

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
python -m yom.toolsets.telegram.example
```

Or programmatically:

```python
import asyncio
from yom import Agent
from yom.toolsets.telegram import TelegramBot

async def main():
    agent = Agent(tools=["core"])
    
    bot = TelegramBot(
        token="123456:ABC-DEF...",
        agent=agent,
    )
    
    print("Bot running! Send a message to try it.")
    await bot.poll()

asyncio.run(main())
```

## 🌐 Production Deployment

### Option A: Polling (Simple)

Best for small scale, testing, or hobby projects.

```bash
# Run in background
nohup python bot.py > bot.log 2>&1 &

# Or use systemd
sudo systemctl enable yom-bot
```

### Option B: Webhook (Recommended)

Best for production - lower latency, more scalable.

#### Prerequisites
- A VPS with a public IP or domain
- HTTPS (required by Telegram)

#### Setup Steps

1. **Set up your VPS**
```bash
# Install nginx + certbot for HTTPS
sudo apt install nginx certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com
```

2. **Configure nginx**
```nginx
# /etc/nginx/sites-available/yom-bot
server {
    listen 443 ssl;
    server_name yourdomain.com;

    location /telegram/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. **Create the bot**
```python
# bot.py
import os
from yom import Agent
from yom.toolsets.telegram import TelegramBot

agent = Agent(tools=["core"])
bot = TelegramBot(token=os.environ["TELEGRAM_BOT_TOKEN"], agent=agent)

# ... webhook handling code from telegram_bot.py
```

4. **Set webhook URL**
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export WEBHOOK_URL="https://yourdomain.com/telegram/webhook"

# Run the bot
python bot.py
```

5. **Point Telegram to your webhook**
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://yourdomain.com/telegram/webhook"
```

## 🐳 Docker Deployment

```bash
# Generate deployment files
python telegram_bot.py generate

# Edit environment variables
nano .env

# Run
docker-compose up -d
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from @BotFather |
| `OPENAI_API_KEY` | Yes | For AI responses |
| `WEBHOOK_URL` | No | Your public URL for webhooks |
| `WEBHOOK_SECRET` | No | Extra security |
| `ALLOWED_USERS` | No | Comma-separated user IDs |
| `SYSTEM_PROMPT` | No | Custom instructions |

## 🔒 Security

### Restrict Access

```python
bot = TelegramBot(
    token="...",
    agent=agent,
    allowed_users=[123456789, 987654321],  # Only these users can chat
)
```

### Verify Webhook Signature

```python
bot.verify_webhook(payload, signature, secret)
```

### Best Practices

1. **Use HTTPS** - Telegram requires it for webhooks
2. **Set allowed_users** - Only allow specific users
3. **Use WEBHOOK_SECRET** - Extra verification layer
4. **Don't log sensitive data** - Hide API keys in logs
5. **Rate limit** - Consider adding rate limiting

## 📊 Monitoring

### Health Check Endpoint

```python
@app.get("/health")
async def health():
    return {"status": "ok", "bot": "running"}
```

### View Logs

```bash
# Docker
docker logs -f yom-telegram-bot

# Systemd
journalctl -u yom-bot -f
```

## 🛠️ Troubleshooting

### Bot not responding?
1. Check token is correct
2. Verify bot was started `/start` in Telegram
3. Check logs for errors

### Webhook not working?
1. Ensure HTTPS is configured
2. Check firewall allows port 443
3. Test endpoint with curl
4. Verify Telegram webhook is set: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

### "Connection refused" errors?
1. Check bot service is running
2. Verify port forwarding in nginx
3. Check firewall rules

## 📱 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/reset` | Clear conversation |
| `/help` | Show help |
| `[message]` | Chat with AI |

## 💬 Example Usage

```
User: Hello, can you help me write a Python function?
Bot: Of course! What would you like the function to do?

User: Calculate the factorial of a number
Bot: Here's a Python function to calculate factorial:

```python
def factorial(n):
    if n < 0:
        raise ValueError("Must be non-negative")
    if n <= 1:
        return 1
    return n * factorial(n - 1)
```

This uses recursion. For large numbers, consider using `math.factorial()` instead.
```
