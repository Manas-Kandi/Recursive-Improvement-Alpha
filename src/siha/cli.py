"""Typer CLI interface"""

from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from siha.db import init_db as init_database, get_session
from siha.agent.loop import AgentLoop
from siha.agent.prompts import seed_default_prompts
from siha.config import settings

app = typer.Typer()
console = Console()


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
    workspace: Path = typer.Option(Path.cwd(), "--workspace", "-w", help="Folder the agent may read/write")
):
    """Interactive chat with the coding agent"""
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    console.print(Panel.fit(
        f"[bold]Self-Improving Harness[/bold]\n"
        f"Model: {model or settings.agent_model}\n"
        f"Sandbox: {sandbox}\n"
        f"Workspace: {workspace}\n"
        f"Type 'exit' to quit",
        title="SIHA Chat"
    ))
    
    agent = AgentLoop(model)
    
    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            if not user_input.strip():
                continue
            
            console.print("[bold magenta]Agent:[/bold magenta] Thinking...")
            
            task = agent.run(user_input, sandbox_mode=sandbox, workspace_dir=workspace)
            
            color = "green" if task.status == "success" else "red"
            console.print(f"[{color}]Task {task.status} in {task.duration_ms}ms[/{color}]")
            if task.final_answer:
                console.print(Panel.fit(task.final_answer, title="Answer"))
            if task.error_summary:
                console.print(f"[red]{task.error_summary}[/red]")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@app.command()
def portal():
    """Launch the developer portal"""
    import uvicorn
    from siha.portal.api import app
    
    console.print("[green]Starting portal backend on http://localhost:8000[/green]")
    console.print(f"[yellow]Auth token: {settings.portal_dev_token}[/yellow]")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)


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
