"""Typer CLI interface"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer
from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from siha.db import init_db as init_database, get_session
from siha.agent.loop import AgentLoop
from siha.agent.prompts import seed_default_prompts
from siha.config import settings
from siha.llm.ollama import is_ollama_reachable
from siha.llm.local_gguf import is_llama_cpp_available
from siha.llm.factory import detect_provider
from siha.models import TaskStatus

app = typer.Typer(no_args_is_help=False)
console = Console()


def _show_main_menu() -> None:
    """Render the interactive main menu."""
    nvidia_ok = bool(settings.nvidia_api_key)
    ollama_ok = is_ollama_reachable()
    local_ok = is_llama_cpp_available()

    status = Text()
    status.append("NVIDIA key: ", style="dim")
    status.append("✓ set" if nvidia_ok else "✗ missing", style="green" if nvidia_ok else "red")
    status.append("  ·  Ollama: ", style="dim")
    status.append("✓ detected" if ollama_ok else "✗ not found", style="green" if ollama_ok else "red")
    status.append("  ·  Local GGUF: ", style="dim")
    status.append("✓ ready" if local_ok else "✗ not installed", style="green" if local_ok else "red")

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()

    table.add_row("1", "Chat with NVIDIA cloud model  [dim](fast, requires API key)[/dim]")
    table.add_row("2", "Chat with local model           [dim](runs on your machine, no API key)[/dim]")
    table.add_row("3", "Launch developer portal         [dim](backend + UI)[/dim]")
    table.add_row("4", "Run benchmarks")
    table.add_row("5", "Trigger self-improvement cycle")
    table.add_row("6", "Init database")
    table.add_row("7", "Exit")

    console.print(Panel.fit(
        Group(
            Text("  ✦ 9xf-code", style="bold bright_white"),
            Text(""),
            status,
            Text(""),
            table,
            Text(""),
            Text("  Type a number to choose, or use subcommands directly:", style="dim"),
            Text("    siha chat | siha portal | siha bench | siha improve | siha init-db", style="dim"),
        ),
        title="[bold bright_white]✦ Main Menu[/bold bright_white]",
        border_style="bright_white",
    ))


def _prompt_provider_choice() -> str:
    """Ask the user which local provider they want."""
    console.print("")
    console.print("  [bold]Local model options:[/bold]")
    console.print("    a) Auto-detect (Ollama → in-process tiny model)")
    console.print("    b) Use Ollama")
    console.print("    c) Use in-process tiny model (auto-download)")
    choice = console.input("  [bold cyan]Choice:[/bold cyan] ").strip().lower()
    if choice == "b":
        return "ollama"
    if choice == "c":
        return "local"
    return "auto"


_TOOL_ICONS: Dict[str, str] = {
    "read_file": "📖",
    "write_file": "✍ ",
    "patch_file": "🩹",
    "bash": "💻",
    "list_files": "📂",
    "search_files": "🔍",
    "run_tests": "🧪",
}
_DEFAULT_ICON = "⚡"

_CODE_EXTS: Dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".sh": "bash", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".html": "html", ".css": "css", ".sql": "sql",
    ".rs": "rust", ".go": "go", ".md": "markdown",
}


@dataclass
class AgentDisplay:
    model: str
    turns: int = 0
    start_time: float = field(default_factory=time.time)
    step: int = 0
    status: str = "idle"
    thought_buffer: str = ""
    reasoning_buffer: str = ""
    current_tool: str = ""
    current_tool_args: Dict[str, Any] = field(default_factory=dict)
    activity_log: List[Tuple[str, str, bool, int]] = field(default_factory=list)

    def add_activity(self, icon: str, label: str, success: bool, duration_ms: int = 0) -> None:
        self.activity_log.append((icon, label, success, duration_ms))
        if len(self.activity_log) > 10:
            self.activity_log.pop(0)

    def render(self) -> Group:
        elapsed = time.time() - self.start_time
        short_model = self.model.split("/")[-1] if "/" in self.model else self.model

        header = Text(justify="left", overflow="fold")
        header.append("  ✦ 9xf-code", style="bold bright_white")
        header.append(f"  ·  {short_model}", style="dim white")
        header.append(f"  ·  step {self.step}", style="dim cyan")
        header.append(f"  ·  {elapsed:.1f}s", style="dim yellow")
        if self.turns > 0:
            header.append(f"  ·  {self.turns}t", style="dim magenta")
        header_panel = Panel(header, border_style="bright_black", padding=(0, 1))

        content_panel = self._render_content()
        activity = self._render_activity()

        return Group(header_panel, content_panel, activity)

    def _render_content(self) -> Panel:
        if self.status == "thinking":
            buf = self.reasoning_buffer or self.thought_buffer
            if buf:
                tail = buf[-500:] if len(buf) > 500 else buf
                is_reasoning = bool(self.reasoning_buffer)
                style = "italic dim cyan" if is_reasoning else "white"
                label = "💭 Reasoning" if is_reasoning else "💭 Thinking"
                return Panel(
                    Text(tail, style=style, overflow="fold"),
                    title=f"[bold cyan]{label}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            return Panel(
                Spinner("dots", text="  Waiting for model...", style="cyan"),
                title="[bold cyan]💭 Thinking[/bold cyan]",
                border_style="cyan dim",
                padding=(0, 1),
            )

        if self.status == "calling_tool":
            icon = _TOOL_ICONS.get(self.current_tool, _DEFAULT_ICON)
            tool_label = Text()
            tool_label.append(f"  {icon}  ", style="bold yellow")
            tool_label.append(self.current_tool, style="bold white")

            args = self.current_tool_args
            code_content: str = args.get("content") or args.get("new_content") or ""
            file_path: str = args.get("path") or args.get("file_path") or ""

            if code_content and len(code_content) > 20:
                ext = Path(file_path).suffix if file_path else ""
                lang = _CODE_EXTS.get(ext, "text")
                snippet = code_content[:700] + ("  …" if len(code_content) > 700 else "")
                code_block = Syntax(
                    snippet, lang, theme="monokai",
                    line_numbers=False, word_wrap=True,
                )
                path_hint = Text()
                if file_path:
                    path_hint.append(f"  → {file_path}", style="dim yellow")
                return Panel(
                    Group(tool_label, path_hint, Padding(code_block, (1, 0, 0, 2))),
                    title="[bold yellow]⚡ Calling Tool[/bold yellow]",
                    border_style="yellow",
                    padding=(0, 1),
                )

            if args:
                rows: List[Text] = []
                for k, v in list(args.items())[:6]:
                    row = Text(overflow="fold")
                    row.append(f"  {k}: ", style="dim")
                    row.append(str(v)[:100], style="white")
                    rows.append(row)
                return Panel(
                    Group(tool_label, *rows),
                    title="[bold yellow]⚡ Calling Tool[/bold yellow]",
                    border_style="yellow",
                    padding=(0, 1),
                )

            return Panel(
                tool_label,
                title="[bold yellow]⚡ Calling Tool[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            )

        if self.status == "done":
            return Panel(
                Text("  ✓  Complete.", style="bold green"),
                border_style="green dim",
                padding=(0, 1),
            )

        return Panel("", border_style="bright_black dim", height=3)

    def _render_activity(self) -> Group:
        if not self.activity_log:
            return Group(Text(""))
        items: List[Text] = []
        for icon, label, success, duration_ms in self.activity_log:
            t = Text(overflow="fold")
            t.append("  ✓  " if success else "  ✗  ", style="bold green" if success else "bold red")
            t.append(f"{icon}  ", style="dim")
            t.append(label, style="white")
            if duration_ms:
                t.append(f"  ·  {duration_ms}ms", style="dim")
            items.append(t)
        return Group(Rule("[dim]Activity[/dim]", style="bright_black"), *items, Text(""))


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context):
    """Interactive menu when called without a subcommand."""
    if ctx.invoked_subcommand is not None:
        return

    while True:
        _show_main_menu()
        choice = console.input("[bold cyan]Choice:[/bold cyan] ").strip()

        if choice == "1":
            if not settings.nvidia_api_key:
                console.print("[red]NVIDIA_API_KEY is not set. Add it to .env and try again.[/red]")
                continue
            chat()
            return
        elif choice == "2":
            provider = _prompt_provider_choice()
            chat(provider=provider)
            return
        elif choice == "3":
            portal()
            return
        elif choice == "4":
            bench()
            return
        elif choice == "5":
            improve()
            return
        elif choice == "6":
            init_db()
            return
        elif choice in ("7", "exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            raise typer.Exit(0)
        else:
            console.print("[red]Invalid choice. Try again.[/red]")


@app.command()
def init_db():
    """Initialize the database"""
    init_database()
    seed_default_prompts()
    console.print("[green]Database initialized and default prompts seeded.[/green]")


@app.command()
def chat(
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
    sandbox: str = typer.Option("local", "--sandbox", "-s", help="Sandbox mode: local or docker"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace", "-w", help="Folder the agent may read/write"),
    provider: str = typer.Option(None, "--provider", "-p", help="LLM provider: nvidia, ollama, local, auto"),
):
    """Interactive chat with the coding agent"""
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    active_model = model or settings.agent_model
    short_model = active_model.split("/")[-1] if "/" in active_model else active_model
    active_provider = (provider or settings.llm_provider).lower()

    console.print(Panel.fit(
        f"[bold]9xf-code[/bold]\n"
        f"Model: [cyan]{short_model}[/cyan]\n"
        f"Provider: [magenta]{active_provider}[/magenta]\n"
        f"Sandbox: {sandbox}   Workspace: {workspace}\n"
        f"[dim]Type 'exit' to quit, 'clear' to reset context[/dim]",
        title="[bold bright_white]✦ 9xf-code[/bold bright_white]",
        border_style="bright_white",
    ))

    agent = AgentLoop(model=model, provider=active_provider)
    conversation_history: List[Dict[str, Any]] = []
    _MAX_HISTORY = 20  # keep last 20 messages (~10 turns)

    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

            if user_input.lower() in ["exit", "quit"]:
                console.print("[dim]Goodbye.[/dim]")
                break

            if user_input.strip().lower() == "clear":
                conversation_history.clear()
                console.print("[dim]Context cleared.[/dim]")
                continue

            if not user_input.strip():
                continue

            turns = len(conversation_history) // 2
            display = AgentDisplay(model=active_model, turns=turns)

            with Live(display.render(), console=console, refresh_per_second=10, transient=True) as live:

                def on_event(event_type: str, data: Dict[str, Any]) -> None:
                    if event_type == "thinking_start":
                        display.status = "thinking"
                        display.step = data.get("step", 0)
                        display.thought_buffer = ""
                        display.reasoning_buffer = ""
                    elif event_type == "reasoning_token":
                        display.reasoning_buffer += data.get("token", "")
                    elif event_type == "content_token":
                        display.thought_buffer += data.get("token", "")
                    elif event_type == "tool_called":
                        display.status = "calling_tool"
                        display.current_tool = data.get("tool", "")
                        display.current_tool_args = data.get("args", {})
                    elif event_type == "tool_result":
                        tool = data.get("tool", "")
                        icon = _TOOL_ICONS.get(tool, _DEFAULT_ICON)
                        success = data.get("success", True)
                        args = display.current_tool_args
                        label = tool
                        if "path" in args:
                            label += f"  {args['path']}"
                        elif "command" in args:
                            label += f"  {str(args['command'])[:50]}"
                        display.add_activity(icon, label, success, data.get("duration_ms", 0))
                        display.status = "thinking"
                    elif event_type == "final_answer":
                        display.status = "done"
                    live.update(display.render())

                task = agent.run(
                    user_input,
                    sandbox_mode=sandbox,
                    workspace_dir=workspace,
                    on_event=on_event,
                    history=conversation_history[-_MAX_HISTORY:] if conversation_history else None,
                )

            # Append this turn to history so the next turn has context
            conversation_history.append({"role": "user", "content": user_input})
            if task.final_answer:
                conversation_history.append({"role": "assistant", "content": task.final_answer})
            elif task.status == TaskStatus.success:
                conversation_history.append({"role": "assistant", "content": "I completed the task."})

            elapsed = f"{(task.duration_ms or 0) / 1000:.1f}s"
            if task.status == TaskStatus.success:
                console.print(f"[bold green]✓[/bold green] [dim]done in {elapsed}[/dim]\n")
            else:
                console.print(f"[bold red]✗[/bold red] [dim]failed in {elapsed}[/dim]\n")

            if task.final_answer:
                console.print(Panel(
                    task.final_answer,
                    title="[bold]Answer[/bold]",
                    border_style="green",
                    padding=(1, 2),
                ))
            if task.error_summary:
                console.print(Panel(
                    task.error_summary,
                    title="[bold red]Error[/bold red]",
                    border_style="red",
                    padding=(0, 1),
                ))

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'exit' to quit.[/dim]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@app.command()
def portal():
    """Launch the developer portal (backend + frontend dev server)"""
    import atexit
    import subprocess
    import uvicorn
    from siha.portal.api import app as api_app

    frontend_dir = Path(__file__).parent.parent.parent / "portal-web"

    if not frontend_dir.exists():
        console.print(f"[red]Frontend not found at {frontend_dir}[/red]")
        raise typer.Exit(1)

    # Install npm dependencies if not present
    if not (frontend_dir / "node_modules" / "vite").exists():
        console.print("[cyan]Installing frontend dependencies (first run)...[/cyan]")
        result = subprocess.run(["npm", "install"], cwd=str(frontend_dir))
        if result.returncode != 0:
            console.print("[red]npm install failed — make sure Node.js is installed.[/red]")
            raise typer.Exit(1)

    # Start Vite dev server in the background
    npm_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def _cleanup():
        npm_proc.terminate()
        try:
            npm_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            npm_proc.kill()

    atexit.register(_cleanup)

    console.print(Panel.fit(
        f"[bold]9xf-code Portal[/bold]\n\n"
        f"  [green]→[/green]  Open [bold cyan]http://localhost:3000[/bold cyan] in your browser\n\n"
        f"  [dim]Backend API:[/dim]  http://localhost:8000\n"
        f"  [dim]Auth token:[/dim]   {settings.portal_dev_token}\n\n"
        f"  [dim]Ctrl+C to stop[/dim]",
        title="[bold bright_white]✦ 9xf-code Portal[/bold bright_white]",
        border_style="bright_white",
    ))

    uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="warning")


@app.command()
def bench():
    """Run benchmarks"""
    from siha.benchmarks.runner import seed_benchmarks, BenchmarkRunner
    from siha.config import settings
    
    console.print("[cyan]Seeding benchmarks...[/cyan]")
    seed_benchmarks()
    
    console.print("[cyan]Running benchmark suite...[/cyan]")
    runner = BenchmarkRunner()
    
    with get_session() as session:
        from siha.models import Benchmark
        benchmarks = session.query(Benchmark).all()
    
    results = []
    for benchmark in benchmarks:
        console.print(f"  Running: {benchmark.name}")
        run = runner.run_benchmark(benchmark, 1)  # Version 1 as baseline
        results.append({
            "name": benchmark.name,
            "score": run.score,
            "passed": run.passed
        })
    
    console.print("\n[green]Benchmark Results:[/green]")
    for r in results:
        status = "[green]✓[/green]" if r["passed"] else "[red]✗[/red]"
        console.print(f"  {status} {r['name']}: {r['score']:.2f}")


@app.command()
def improve():
    """Trigger self-improvement analysis"""
    from siha.harness.scheduler import Scheduler
    
    console.print("[cyan]Triggering improvement cycle...[/cyan]")
    scheduler = Scheduler()
    scheduler.trigger_improvement()
    console.print("[green]Improvement cycle complete[/green]")


if __name__ == "__main__":
    app()
