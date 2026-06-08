"""Typer CLI interface."""

from pathlib import Path
from typing import Optional

import typer

from siha.config import settings
from siha.llm.ollama import is_ollama_reachable
from siha.llm.local_gguf import is_llama_cpp_available
from siha.cli_display import console, show_main_menu, prompt_provider_choice
from siha.cli_commands import cmd_init_db, cmd_chat, cmd_portal, cmd_bench, cmd_improve

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context):
    """Interactive menu when called without a subcommand."""
    if ctx.invoked_subcommand is not None:
        return

    nvidia_ok = bool(settings.nvidia_api_key)
    ollama_ok = is_ollama_reachable()
    local_ok = is_llama_cpp_available()

    while True:
        show_main_menu(nvidia_ok, ollama_ok, local_ok)
        choice = console.input("[bold cyan]Choice:[/bold cyan] ").strip()

        if choice == "1":
            if not settings.nvidia_api_key:
                console.print("[red]NVIDIA_API_KEY is not set. Add it to .env and try again.[/red]")
                continue
            cmd_chat(model=None, sandbox="local", workspace=Path.cwd(), provider=None)
            return
        elif choice == "2":
            provider = prompt_provider_choice()
            cmd_chat(model=None, sandbox="local", workspace=Path.cwd(), provider=provider)
            return
        elif choice == "3":
            cmd_portal()
            return
        elif choice == "4":
            cmd_bench()
            return
        elif choice == "5":
            cmd_improve()
            return
        elif choice == "6":
            cmd_init_db()
            return
        elif choice in ("7", "exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            raise typer.Exit(0)
        else:
            console.print("[red]Invalid choice. Try again.[/red]")


@app.command()
def init_db():
    """Initialize the database."""
    cmd_init_db()


@app.command()
def chat(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    sandbox: str = typer.Option("local", "--sandbox", "-s", help="Sandbox mode: local or docker"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", "-w", help="Folder the agent may read/write"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider: nvidia, ollama, local, auto"),
):
    """Interactive chat with the coding agent."""
    cmd_chat(model=model, sandbox=sandbox, workspace=workspace, provider=provider)


@app.command()
def portal():
    """Launch the developer portal (backend + frontend dev server)."""
    cmd_portal()


@app.command()
def bench():
    """Run benchmarks."""
    cmd_bench()


@app.command()
def improve():
    """Trigger self-improvement analysis."""
    cmd_improve()


if __name__ == "__main__":
    app()
