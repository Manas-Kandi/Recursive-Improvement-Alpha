"""Individual CLI command implementations."""

from pathlib import Path
from typing import Any, Dict, List

import typer
from rich.panel import Panel
from rich.live import Live

from siha.db import init_db as init_database, get_session
from sqlmodel import select
from siha.agent.loop import AgentLoop
from siha.agent.prompts import seed_default_prompts
from siha.config import settings
from siha.models import TaskStatus
from siha.cli_display import console, AgentDisplay, _TOOL_ICONS, _DEFAULT_ICON


def cmd_init_db() -> None:
    """Initialize the database."""
    from siha.agent.action_mapper import seed_default_templates

    init_database()
    seed_default_prompts()
    seed_default_templates()
    console.print("[green]Database initialized; default prompts and action templates seeded.[/green]")


def cmd_chat(
    model: str | None,
    sandbox: str,
    workspace: Path,
    provider: str | None,
) -> None:
    """Interactive chat with the coding agent."""
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    active_model = model or settings.agent_model
    short_model = active_model.split("/")[-1] if "/" in active_model else active_model
    active_provider = (provider or settings.llm_provider).lower()

    console.print(Panel.fit(
        f"[bold]SIHA[/bold]\n"
        f"Model: [cyan]{short_model}[/cyan]\n"
        f"Provider: [magenta]{active_provider}[/magenta]\n"
        f"Sandbox: {sandbox}   Workspace: {workspace}\n"
        f"[dim]Type 'exit' to quit, 'clear' to reset context[/dim]",
        title="[bold bright_white]SIHA[/bold bright_white]",
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
                console.print(f"[bold green]OK[/bold green] [dim]done in {elapsed}[/dim]\n")
            else:
                console.print(f"[bold red]FAIL[/bold red] [dim]failed in {elapsed}[/dim]\n")

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


def cmd_portal() -> None:
    """Launch the developer portal (backend + frontend dev server)."""
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
            console.print("[red]npm install failed -- make sure Node.js is installed.[/red]")
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
        f"[bold]SIHA Portal[/bold]\n\n"
        f"  [green]->[/green]  Open [bold cyan]http://localhost:3000[/bold cyan] in your browser\n\n"
        f"  [dim]Backend API:[/dim]  http://localhost:8000\n"
        f"  [dim]Auth token:[/dim]   {settings.portal_dev_token}\n\n"
        f"  [dim]Ctrl+C to stop[/dim]",
        title="[bold bright_white]SIHA Portal[/bold bright_white]",
        border_style="bright_white",
    ))

    uvicorn.run(api_app, host="0.0.0.0", port=8000, log_level="warning")


def cmd_bench() -> None:
    """Run benchmarks."""
    from siha.benchmarks.runner import seed_benchmarks, BenchmarkRunner

    console.print("[cyan]Seeding benchmarks...[/cyan]")
    seed_benchmarks()

    console.print("[cyan]Running benchmark suite...[/cyan]")
    runner = BenchmarkRunner()

    with get_session() as session:
        from siha.models import Benchmark
        benchmarks = session.exec(select(Benchmark)).all()

    results = []
    for benchmark in benchmarks:
        console.print(f"  Running: {benchmark.name}")
        run = runner.run_benchmark(benchmark, None)  # Use default active harness
        results.append({
            "name": benchmark.name,
            "score": run.score,
            "passed": run.passed,
        })

    console.print("\n[green]Benchmark Results:[/green]")
    for r in results:
        status = "[green]OK[/green]" if r["passed"] else "[red]FAIL[/red]"
        console.print(f"  {status} {r['name']}: {r['score']:.2f}")


def cmd_improve() -> None:
    """Trigger self-improvement analysis."""
    from siha.harness.scheduler import Scheduler

    console.print("[cyan]Triggering improvement cycle...[/cyan]")
    scheduler = Scheduler()
    scheduler.trigger_improvement()
    console.print("[green]Improvement cycle complete[/green]")
