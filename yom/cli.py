"""CLI entrypoint for agent-core."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

try:
    import click
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
except ImportError:
    print("CLI extras not installed. Run: pip install agent-core[cli]")
    sys.exit(1)

from yom import AgentRuntime, RuntimeSettings, build_runtime, build_runtime_from_yaml, tool
from yom.models import RuntimeRunResult


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """agent-core CLI - Configurable agent runtime."""
    pass


@main.command()
@click.argument("prompt", required=False)
@click.option("--config", "-c", type=click.Path(exists=True), help="YAML config file")
@click.option("--session-id", "-s", help="Session ID to resume")
@click.option("--runtime-id", default="cli", help="Runtime ID")
@click.option("--system-prompt", default=None, help="System prompt")
@click.option("--model", "-m", default=None, help="Default model")
def run(
    prompt: Optional[str],
    config: Optional[str],
    session_id: Optional[str],
    runtime_id: str,
    system_prompt: Optional[str],
    model: Optional[str],
):
    """Run a prompt through the agent."""
    if not prompt:
        console.print("[yellow]Usage: agent run \"your prompt\"[/yellow]")
        return

    try:
        if config:
            runtime = build_runtime_from_yaml(config)
        else:
            settings = RuntimeSettings(
                runtime_id=runtime_id,
                system_prompt=system_prompt or "You are a helpful assistant.",
                default_model=model,
            )
            runtime = build_runtime(settings)
    except Exception as e:
        console.print(f"[red]Failed to create runtime: {e}[/red]")
        sys.exit(1)

    console.print(Panel(f"[bold cyan]Prompt:[/bold cyan]\n{prompt}", title="Agent Input"))

    async def _run():
        result: RuntimeRunResult = await runtime.run_prompt(
            prompt=prompt,
            session_id=session_id,
        )
        return result

    try:
        result = asyncio.run(_run())

        if result.error:
            console.print(Panel(
                f"[bold red]Error:[/bold red] {result.error}",
                title="Result",
                border_style="red"
            ))
        else:
            console.print(Panel(
                f"[green]{result.final_message}[/green]",
                title="Agent Response",
                border_style="green"
            ))
            if result.usage:
                console.print(f"[dim]Usage: {result.usage}[/dim]")
    except Exception as e:
        console.print(f"[red]Execution error: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="YAML config file")
def repl(config: Optional[str]):
    """Start an interactive REPL session."""
    console.print("[bold green]agent-core REPL[/bold green]")
    console.print("Type 'exit' to quit, 'help' for commands\n")

    try:
        if config:
            runtime = build_runtime_from_yaml(config)
        else:
            settings = RuntimeSettings(
                runtime_id="repl",
                system_prompt="You are a helpful assistant. Keep responses concise.",
            )
            runtime = build_runtime(settings)
    except Exception as e:
        console.print(f"[red]Failed to create runtime: {e}[/red]")
        sys.exit(1)

    session_id = None
    history: list[str] = []

    async def _run_prompt(prompt_text: str):
        nonlocal session_id
        result = await runtime.run_prompt(prompt=prompt_text, session_id=session_id)
        session_id = result.session_id
        return result

    while True:
        try:
            user_input = console.input("\n[bold blue>[/bold blue] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        if not user_input.strip():
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[yellow]Goodbye![/yellow]")
            break

        if user_input.lower() == "help":
            console.print("""
[bold]Commands:[/bold]
  exit, quit, q   - Exit the REPL
  history, hist   - Show conversation history
  clear           - Clear screen
  help            - Show this help
""")
            continue

        if user_input.lower() in ("history", "hist"):
            for i, msg in enumerate(history):
                prefix = "[cyan]User[/cyan]" if i % 2 == 0 else "[green]Agent[/green]"
                console.print(f"{prefix}: {msg[:100]}...")
            continue

        if user_input.lower() == "clear":
            console.clear()
            continue

        console.print("[dim]Thinking...[/dim]", end="\r")

        async def _repl():
            return await _run_prompt(user_input)

        result = asyncio.run(_repl())
        history.append(user_input)
        history.append(result.final_message)

        console.print(f"\n[bold green]Agent:[/bold green] {result.final_message}")

        if result.error:
            console.print(f"[red]Error: {result.error}[/red]")


@main.command()
def tools():
    """List available tools."""
    settings = RuntimeSettings(runtime_id="cli", system_prompt="")
    runtime = build_runtime(settings)

    tool_list = runtime.list_tools()
    if not tool_list:
        console.print("[yellow]No tools configured[/yellow]")
        return

    console.print("[bold]Available tools:[/bold]")
    for tool in tool_list:
        name = getattr(tool, "_tool_name", None) or getattr(tool, "name", "unknown")
        desc = getattr(tool, "_tool_description", "") or getattr(tool, "description", "")
        console.print(f"  [cyan]{name}[/cyan]: {desc}")


@main.command()
@click.argument("session_id")
def session(session_id: str):
    """Show session info (placeholder)."""
    console.print(f"[yellow]Session management not yet implemented[/yellow]")
    console.print(f"Session ID: {session_id}")


@main.command()
@click.option("--config", "-c", type=click.Path(exists=True), help="YAML config file")
def validate(config: Optional[str]):
    """Validate configuration."""
    try:
        if config:
            runtime = build_runtime_from_yaml(config)
            console.print(f"[green]Configuration valid:[/green] {config}")
            console.print(f"  Runtime ID: {runtime.settings.runtime_id}")
            console.print(f"  System prompt: {runtime.settings.get_system_prompt()[:50]}...")
            console.print(f"  Tools: {len(runtime.list_tools())}")
        else:
            console.print("[yellow]No config file provided[/yellow]")
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


def main_CLI():
    """Entry point for console script."""
    main()


if __name__ == "__main__":
    main()