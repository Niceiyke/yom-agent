"""CLI entrypoint for yom."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from yom import Agent, RuntimeSettings, build_runtime, build_runtime_from_yaml
from yom.models import RuntimeRunResult

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.1")
def main():
    """yom - Agent runtime CLI
    
    Usage:
        yom init <name>          Create new agent project
        yom run "prompt"         Run a prompt
        yom chat                 Interactive chat
        yom repl                 REPL mode
    """
    pass


# =============================================================================
# INIT COMMAND - Create new agent project
# =============================================================================

@main.command()
@click.argument("name")
@click.option("--template", "-t", default="basic", 
              type=click.Choice(["basic", "telegram", "api", "multi-agent"]),
              help="Project template")
@click.option("--dir", "-d", default=None, help="Target directory")
def init(name: str, template: str, dir: Optional[str]):
    """Create a new yom agent project.
    
    Examples:
        yom init my-agent
        yom init my-agent --template telegram
        yom init api-service --dir /path/to/projects
    """
    target_dir = Path(dir) / name if dir else Path.cwd() / name
    
    if target_dir.exists() and any(target_dir.iterdir()):
        if not click.confirm(f"Directory {target_dir} exists and is not empty. Continue?"):
            console.print("[yellow]Aborted.[/yellow]")
            return
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    templates = {
        "basic": _create_basic_template,
        "telegram": _create_telegram_template,
        "api": _create_api_template,
        "multi-agent": _create_multi_agent_template,
    }
    
    templates[template](target_dir, name)
    
    console.print(Panel(
        f"[green]✅ Created {name} at {target_dir}[/green]\n\n"
        f"Template: [cyan]{template}[/cyan]\n\n"
        f"Next steps:\n"
        f"  cd {name}\n"
        f"  # Edit agent.yaml and tools/\n"
        f"  yom run --config agent.yaml \"Hello\"",
        title="Project Created"
    ))


def _create_basic_template(target: Path, name: str):
    """Create basic agent template."""
    # Create directory structure
    (target / "tools").mkdir(exist_ok=True)
    (target / "sessions").mkdir(exist_ok=True)
    
    # Create agent.yaml
    agent_yaml = f'''runtime_id: "{name}"
system_prompt: "You are a helpful assistant."

provider:
  name: "minimax"  # or openai, anthropic, etc.
  model: "MiniMax-M2.7"

tools:
  - "core"

session:
  backend: "memory"
'''
    (target / "agent.yaml").write_text(agent_yaml)
    
    # Create main.py
    main_py = '''"""Main entry point for yom agent."""

from yom import Agent

def main():
    agent = Agent(config="agent.yaml")
    
    while True:
        prompt = input("You: ")
        if prompt.lower() in ("exit", "quit"):
            break
        response = agent.run_sync(prompt)
        print(f"Agent: {response}")

if __name__ == "__main__":
    main()
'''
    (target / "main.py").write_text(main_py)
    
    # Create tools/__init__.py
    (target / "tools" / "__init__.py").write_text('"""Custom tools for this agent."""\n')
    
    # Create README.md
    readme = f'''# {name}

A yom agent project.

## Setup

```bash
pip install yom
export MINIMAX_API_KEY=your_key_here
```

## Run

```bash
yom run --config agent.yaml "Your prompt"
```

## Develop

Edit `agent.yaml` to configure the agent.
Add custom tools in `tools/` directory.
'''
    (target / "README.md").write_text(readme)


def _create_telegram_template(target: Path, name: str):
    """Create Telegram bot template."""
    _create_basic_template(target, name)
    
    # Create bot.py
    bot_py = '''"""Telegram bot for yom agent."""

from yom import Agent
from yom.toolsets.telegram import TelegramBot

def main():
    import os
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Set TELEGRAM_BOT_TOKEN environment variable")
    
    agent = Agent(tools=["core"])
    bot = TelegramBot(token=token, agent=agent)
    
    print("Bot started! Press Ctrl+C to stop.")
    asyncio.run(bot.poll())

if __name__ == "__main__":
    main()
'''
    (target / "bot.py").write_text(bot_py)
    
    # Update agent.yaml
    agent_yaml = f'''runtime_id: "{name}"
system_prompt: "You are a helpful assistant. Be friendly and concise."

provider:
  name: "minimax"
  model: "MiniMax-M2.7"

tools:
  - "core"

telegram:
  enabled: true
'''
    (target / "agent.yaml").write_text(agent_yaml)
    
    # Update README
    readme = f'''# {name} - Telegram Bot

A yom agent with Telegram integration.

## Setup

```bash
export MINIMAX_API_KEY=your_key
export TELEGRAM_BOT_TOKEN=your_token
```

## Run

```bash
python bot.py
# or
yom telegram polling --token $TELEGRAM_BOT_TOKEN --tools "core"
```
'''
    (target / "README.md").write_text(readme)


def _create_api_template(target: Path, name: str):
    """Create API server template."""
    _create_basic_template(target, name)
    
    # Create api.py
    api_py = '''"""FastAPI server for yom agent."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from yom import Agent

app = FastAPI(title="yom Agent API")

# Initialize agent
agent = Agent(config="agent.yaml")


class PromptRequest(BaseModel):
    prompt: str
    session_id: str | None = None


class PromptResponse(BaseModel):
    response: str
    session_id: str


@app.post("/prompt")
async def prompt(request: PromptRequest):
    """Process a prompt."""
    agent = Agent(session_id=request.session_id, config="agent.yaml")
    result = await agent.run(request.prompt)
    return PromptResponse(response=result, session_id=agent.session_id)


@app.get("/sessions")
async def list_sessions():
    """List active sessions."""
    return {"sessions": []}


@app.get("/sessions/{{session_id}}")
async def get_session(session_id: str):
    """Get session history."""
    return {"session_id": session_id, "messages": []}


@app.delete("/sessions/{{session_id}}")
async def delete_session(session_id: str):
    """Delete a session."""
    return {"deleted": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    (target / "api.py").write_text(api_py)
    
    # Update README
    readme = f'''# {name} - API Server

A yom agent with FastAPI web interface.

## Setup

```bash
pip install yom fastapi uvicorn
export MINIMAX_API_KEY=your_key
```

## Run

```bash
uvicorn api:app --reload
```

## Endpoints

- `POST /prompt` - Send a prompt
- `GET /sessions` - List sessions
- `GET /sessions/{{id}}` - Get session
- `DELETE /sessions/{{id}}` - Delete session
'''
    (target / "README.md").write_text(readme)


def _create_multi_agent_template(target: Path, name: str):
    """Create multi-agent template."""
    _create_basic_template(target, name)
    
    # Create agents directory
    (target / "agents").mkdir(exist_ok=True)
    
    # Create supervisor.py
    supervisor_py = '''"""Supervisor agent that coordinates sub-agents."""

from yom import Agent

def main():
    supervisor = Agent(
        system_prompt="""You are a supervisor that coordinates multiple specialized agents.
Available agents:
- coder: Writes code
- reviewer: Reviews code
- tester: Writes tests

Delegate tasks to the appropriate agent.""",
        tools=["core"],
    )
    
    # Example: delegate coding task
    result = supervisor.run_sync(
        "Have the coder write a hello world function, "
        "then have the reviewer check it."
    )
    print(result)

if __name__ == "__main__":
    main()
'''
    (target / "supervisor.py").write_text(supervisor_py)
    
    # Create agents/README.md
    agents_readme = '''# Sub-Agents

Define specialized agents here.

Each agent is a YAML file with name, system_prompt, and tools.

Example (coder.yaml):
```yaml
name: coder
system_prompt: "You are an expert programmer. Write clean, efficient code."
tools:
  - "core"
  - "shell"
```
'''
    (target / "agents" / "README.md").write_text(agents_readme)
    
    # Update README
    readme = f'''# {name} - Multi-Agent

A yom agent that coordinates multiple specialized sub-agents.

## Structure

```
{name}/
├── supervisor.py     # Main supervisor agent
├── agents/           # Sub-agent definitions
│   ├── coder.yaml
│   ├── reviewer.yaml
│   └── tester.yaml
└── agent.yaml
```

## Run

```bash
python supervisor.py
```
'''
    (target / "README.md").write_text(readme)


# =============================================================================
# RUN COMMAND - Run a prompt
# =============================================================================

@main.command()
@click.argument("prompt", required=False)
@click.option("--config", "-c", type=click.Path(exists=True), help="YAML config file")
@click.option("--session-id", "-s", default=None, help="Session ID to use")
@click.option("--system-prompt", default=None, help="System prompt override")
@click.option("--model", "-m", default=None, help="Model override")
@click.option("--tools", "-t", default=None, help="Comma-separated tools")
def run(prompt: Optional[str], config: Optional[str], session_id: Optional[str], 
        system_prompt: Optional[str], model: Optional[str], tools: Optional[str]):
    """Run a prompt through the agent.
    
    Examples:
        yom run "What is 2+2?"
        yom run --config agent.yaml "Hello"
        yom run -s my-session "Continue from where we left off"
    """
    if not prompt:
        console.print("[yellow]Usage: yom run \"your prompt\"[/yellow]")
        console.print("[dim]Or use: yom chat (interactive mode)[/dim]")
        return
    
    # Determine tools
    tool_list = None
    if tools:
        tool_list = [t.strip() for t in tools.split(",")]
    
    # Build agent
    try:
        if config:
            import yaml
            with open(config) as f:
                cfg = yaml.safe_load(f)
            
            # Get provider config
            provider_cfg = cfg.get("provider", {})
            
            agent = Agent(
                system_prompt=cfg.get("system_prompt", "You are helpful."),
                model=provider_cfg.get("model"),
                session_id=session_id,
            )
            # Set tools
            if "tools" in cfg:
                agent._resolved_tools = agent._resolve_tools()
                # Re-init with tools
                original_tools = agent.tools
                agent = Agent(
                    system_prompt=cfg.get("system_prompt", "You are helpful."),
                    model=provider_cfg.get("model"),
                    tools=cfg.get("tools", ["core"]),
                    session_id=session_id,
                )
        else:
            agent_kwargs = {
                "session_id": session_id,
                "system_prompt": system_prompt or "You are a helpful assistant.",
            }
            if tool_list:
                agent_kwargs["tools"] = tool_list
            if model:
                agent_kwargs["model"] = model
            agent = Agent(**agent_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to create agent: {e}[/red]")
        sys.exit(1)
    
    console.print(Panel(
        f"[bold cyan]Prompt:[/bold cyan]\n{prompt}",
        title="Input",
        border_style="blue"
    ))
    console.print("[dim]Thinking...[/dim]", end="\r")
    
    try:
        result = agent.run_sync(prompt)
        console.print("\r" + " " * 20 + "\r")  # Clear "Thinking..."
        
        console.print(Panel(
            f"[green]{result}[/green]",
            title="Agent Response",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"\r[red]Error: {e}[/red]")
        sys.exit(1)


# =============================================================================
# CHAT COMMAND - Interactive chat
# =============================================================================

@main.command()
@click.option("--session-id", "-s", default=None, help="Session ID")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file")
@click.option("--system-prompt", default=None, help="System prompt")
def chat(session_id: Optional[str], config: Optional[str], system_prompt: Optional[str]):
    """Start an interactive chat session.
    
    Examples:
        yom chat
        yom chat --session alice
        yom chat -c agent.yaml
    """
    console.print(Panel(
        "[bold green]yom Chat[/bold green]\n"
        "Type 'exit' to quit, 'clear' to clear screen, 'help' for more commands.",
        title="Chat Started"
    ))
    
    # Build agent
    try:
        if config:
            agent = Agent(config=config, session_id=session_id)
        else:
            agent = Agent(
                session_id=session_id or "chat",
                system_prompt=system_prompt or "You are a helpful assistant.",
            )
    except Exception as e:
        console.print(f"[red]Failed to create agent: {e}[/red]")
        sys.exit(1)
    
    console.print(f"[dim]Session: {agent.session_id}[/dim]\n")
    
    history = []
    
    while True:
        try:
            user_input = console.input("\n[cyan]You:[/cyan] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        
        if not user_input.strip():
            continue
        
        cmd = user_input.lower().strip()
        
        if cmd in ("exit", "quit", "q"):
            console.print("[yellow]Goodbye![/yellow]")
            break
        
        if cmd == "clear":
            console.clear()
            console.print(f"[dim]Session: {agent.session_id}[/dim]\n")
            continue
        
        if cmd == "help":
            console.print("""
[bold]Commands:[/bold]
  exit, quit, q   - Exit chat
  clear          - Clear screen
  history, hist  - Show conversation history
  session        - Show current session ID
  reset          - Reset conversation (new session)
  help           - Show this help
""")
            continue
        
        if cmd in ("history", "hist"):
            if not history:
                console.print("[dim]No history yet[/dim]")
            else:
                for i, (role, msg) in enumerate(history):
                    prefix = "[cyan]You[/cyan]" if role == "user" else "[green]Agent[/green]"
                    console.print(f"{prefix}: {msg[:80]}...")
            continue
        
        if cmd == "session":
            console.print(f"[dim]Current session: {agent.session_id}[/dim]")
            continue
        
        if cmd == "reset":
            agent = Agent(
                session_id=None,  # New session
                system_prompt=system_prompt or "You are a helpful assistant.",
            )
            history.clear()
            console.print(f"[dim]New session: {agent.session_id}[/dim]\n")
            continue
        
        # Regular prompt
        console.print("[dim]Thinking...[/dim]", end="\r")
        
        try:
            result = agent.run_sync(user_input)
            console.print("\r" + " " * 20 + "\r")
            console.print(f"[bold green]Agent:[/bold green] {result}")
            
            history.append(("user", user_input))
            history.append(("assistant", result))
        except Exception as e:
            console.print(f"\r[red]Error: {e}[/red]")


# =============================================================================
# REPL COMMAND - Simple REPL
# =============================================================================

@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file")
@click.option("--no-stream", is_flag=True, help="Disable streaming (show complete response)")
@click.option("--model", "-m", default=None, help="Model to use")
@click.option("--base-url", "-b", default=None, help="API base URL")
def repl(config, no_stream, model, base_url):
    """Start a REPL session with streaming by default.
    
    Examples:
        yom repl
        yom repl -c agent.yaml
        yom repl --no-stream
        yom repl -m MiniMax-M2.7
    """
    console.print("[bold green]yom REPL[/bold green] (streaming enabled by default)")
    console.print("Type 'exit' to quit, 'help' for commands\n")
    
    try:
        agent_kwargs = {
            "system_prompt": "You are helpful. Keep responses concise.",
        }
        
        # Apply model and base_url from CLI args
        if model:
            agent_kwargs["model"] = model
        if base_url:
            agent_kwargs["base_url"] = base_url
            # Also set env for provider
            os.environ["YOM_BASE_URL"] = base_url
        
        if config:
            agent_kwargs["config"] = config
        
        agent = Agent(**agent_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to create agent: {e}[/red]")
        sys.exit(1)
    
    session_id = None
    history = []
    streaming = not no_stream
    
    while True:
        try:
            user_input = console.input("\n[cyan]>[/cyan] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        
        if not user_input.strip():
            continue
        
        cmd = user_input.lower().strip()
        
        if cmd in ("exit", "quit", "q"):
            console.print("[yellow]Goodbye![/yellow]")
            break
        
        if cmd == "help":
            console.print("""
[bold]Commands:[/bold]
  exit, quit, q   - Exit REPL
  history, hist   - Show history
  clear           - Clear screen
  session         - Show session ID
  reset           - Reset session
  stream on/off   - Toggle streaming
  help            - Show help
""")
            continue
        
        if cmd == "stream on":
            streaming = True
            console.print("[dim]Streaming enabled[/dim]")
            continue
        
        if cmd == "stream off":
            streaming = False
            console.print("[dim]Streaming disabled[/dim]")
            continue
        
        if cmd in ("history", "hist"):
            for i, msg in enumerate(history):
                prefix = "[cyan]User[/cyan]" if i % 2 == 0 else "[green]Agent[/green]"
                console.print(f"{prefix}: {msg[:80]}...")
            continue
        
        if cmd == "clear":
            console.clear()
            continue
        
        if cmd == "session":
            console.print(f"[dim]Session: {session_id}[/dim]")
            continue
        
        if cmd == "reset":
            session_id = None
            history.clear()
            console.print("[dim]Session reset[/dim]")
            continue
        
        console.print("[dim]Thinking...[/dim]", end="\r")
        
        try:
            if streaming:
                # Streaming mode with tool visibility
                console.print("\r" + " " * 20 + "\r")
                console.print("\n[bold green]Agent:[/bold green] ", end="")
                
                collected = []
                tool_count = [0]
                
                def on_chunk(text):
                    console.print(text, end="")
                    collected.append(text)
                
                def on_tool(name, args):
                    tool_count[0] += 1
                    # Show tool call inline
                    console.print(f"\n[dim]\n[Using tool: {name}][/dim]", end="")
                
                asyncio.run(agent.run_stream(
                    user_input,
                    stream_callback=on_chunk,
                    tool_callback=on_tool,
                ))
                
                console.print()  # newline after streaming
                result = "".join(collected)
                history.append(user_input)
                history.append(result)
            else:
                # Non-streaming mode
                result = agent.run_sync(user_input)
                console.print("\r" + " " * 20 + "\r")
                console.print(f"\n[bold green]Agent:[/bold green] {result}")
                history.append(user_input)
                history.append(result)
        except Exception as e:
            console.print(f"\r[red]Error: {e}[/red]")


# =============================================================================
# SESSIONS COMMAND - Session management
# =============================================================================

@main.group()
def sessions():
    """Manage agent sessions.
    
    Examples:
        yom sessions list
        yom sessions clear alice
        yom sessions export alice
    """
    pass


@sessions.command("list")
@click.option("--dir", "-d", default=None, help="Session storage directory")
def sessions_list(dir: Optional[str]):
    """List all sessions."""
    # For now, just show info about session management
    console.print("[bold]Session Management[/bold]")
    
    table = Table(show_header=True)
    table.add_column("Command")
    table.add_column("Description")
    
    table.add_row("yom sessions list", "List active sessions")
    table.add_row("yom sessions clear <id>", "Clear a session")
    table.add_row("yom sessions export <id>", "Export session to JSON")
    table.add_row("yom sessions import <id>", "Import session from JSON")
    
    console.print(table)
    console.print("\n[dim]Note: Sessions are stored in memory by default.[/dim]")


@sessions.command("clear")
@click.argument("session_id")
def sessions_clear(session_id: str):
    """Clear a session."""
    console.print(f"[green]Cleared session: {session_id}[/green]")
    console.print("[dim](Memory backend - sessions auto-clear on restart)[/dim]")


@sessions.command("export")
@click.argument("session_id")
@click.option("--output", "-o", default=None, help="Output file path")
def sessions_export(session_id: str, output: Optional[str]):
    """Export a session to JSON."""
    output_path = Path(output) if output else Path(f"{session_id}.json")
    console.print(f"[green]Would export {session_id} to {output_path}[/green]")


@sessions.command("import")
@click.argument("file")
@click.option("--session-id", "-s", default=None, help="Session ID to import as")
def sessions_import(file: str, session_id: Optional[str]):
    """Import a session from JSON."""
    sid = session_id or "imported"
    console.print(f"[green]Would import {file} as session {sid}[/green]")


# =============================================================================
# DEBUG COMMAND - Debug utilities
# =============================================================================

@main.command()
@click.option("--session", "-s", default=None, help="Session to trace")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def debug(session: Optional[str], verbose: bool):
    """Debug session or agent state.
    
    Examples:
        yom debug
        yom debug --session my-session -v
    """
    from yom.debug import enable_debug, get_recorder
    
    enable_debug()
    
    console.print("[bold green]Debug Mode Enabled[/bold green]")
    
    if session:
        console.print(f"[dim]Tracing session: {session}[/dim]")
    
    recorder = get_recorder()
    console.print(f"[dim]Recorded events: {len(recorder.events)}[/dim]")
    
    if verbose and recorder.events:
        console.print("\n[bold]Recent Events:[/bold]")
        for event in recorder.events[-10:]:
            console.print(f"  [dim]{event}[/dim]")


@main.command()
@click.argument("session_id")
def inspect(session_id: str):
    """Inspect session state."""
    console.print(f"[bold]Inspecting session: {session_id}[/bold]")
    console.print("[dim](Full inspection not yet implemented)[/dim]")


# =============================================================================
# INFO COMMAND - Show info
# =============================================================================

@main.command()
def info():
    """Show yom information."""
    from yom import __version__
    
    table = Table(title="yom Info")
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Version", __version__)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Location", str(Path(__file__).parent.parent))
    
    console.print(table)
    
    # Show available toolsets
    console.print("\n[bold]Available toolsets:[/bold]")
    from yom.toolsets import __all__
    for toolset in __all__:
        if not toolset.startswith("Telegram"):
            console.print(f"  [cyan]{toolset}[/cyan]")


# =============================================================================
# TEMPLATE COMMAND - List/create templates
# =============================================================================

@main.command()
def templates():
    """List available project templates."""
    table = Table(title="Available Templates")
    table.add_column("Name")
    table.add_column("Description")
    
    table.add_row("basic", "Simple agent with config file")
    table.add_row("telegram", "Telegram bot integration")
    table.add_row("api", "FastAPI web service")
    table.add_row("multi-agent", "Supervisor with sub-agents")
    
    console.print(table)
    console.print("\n[dim]Usage: yom init <name> --template <template>[/dim]")


# =============================================================================
# TELEGRAM COMMANDS
# =============================================================================

@main.group()
def telegram():
    """Telegram bot commands.
    
    Examples:
        yom telegram polling --token <token>
        yom telegram set-webhook --token <token> --url <url>
    """
    pass


@telegram.command("polling")
@click.option("--token", "-t", required=True, help="Telegram bot token")
@click.option("--tools", default="core", help="Comma-separated tools")
@click.option("--system-prompt", default=None, help="System prompt")
def telegram_polling(token: str, tools: str, system_prompt: Optional[str]):
    """Run Telegram bot with polling."""
    from yom.toolsets.telegram import TelegramBot
    
    tool_list = [t.strip() for t in tools.split(",")]
    agent = Agent(tools=tool_list, system_prompt=system_prompt or "You are helpful.")
    bot = TelegramBot(token=token, agent=agent)
    
    console.print(f"[green]🤖 Bot started![/green]")
    console.print(f"[dim]Tools: {', '.join(tool_list)}[/dim]")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]")
    
    try:
        asyncio.run(bot.poll())
    except KeyboardInterrupt:
        bot.stop()
        console.print("\n[green]👋 Bot stopped.[/green]")


@telegram.command("set-webhook")
@click.option("--token", "-t", required=True, help="Telegram bot token")
@click.option("--url", "-u", required=True, help="Webhook URL")
def telegram_set_webhook(token: str, url: str):
    """Set webhook URL for the bot."""
    import httpx
    
    async def set_wh():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/setWebhook",
                json={"url": url}
            )
            result = response.json()
            if result.get("ok"):
                console.print(f"[green]✅ Webhook set to {url}[/green]")
            else:
                console.print(f"[red]❌ Error: {result.get('description')}[/red]")
    
    asyncio.run(set_wh())


@telegram.command("get-updates")
@click.option("--token", "-t", required=True, help="Telegram bot token")
def telegram_get_updates(token: str):
    """Get pending updates."""
    import httpx
    
    async def get_upd():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates"
            )
            result = response.json()
            if result.get("ok"):
                updates = result.get("result", [])
                console.print(f"[green]{len(updates)} pending update(s)[/green]")
                for u in updates[:5]:
                    msg = u.get("message", {})
                    console.print(f"  [dim]{msg.get('from', {}).get('first_name', '?')}: {msg.get('text', '')}[/dim]")
            else:
                console.print(f"[red]❌ Error: {result.get('description')}[/red]")
    
    asyncio.run(get_upd())


# =============================================================================
# ENTRY POINT
# =============================================================================

def main_CLI():
    """Entry point for console script."""
    main()


if __name__ == "__main__":
    main()