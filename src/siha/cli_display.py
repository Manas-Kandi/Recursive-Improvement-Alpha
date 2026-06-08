"""Rich display helpers for the CLI."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich.console import Console
from rich.panel import Panel
try:
    from rich.group import Group
except ImportError:
    from rich.console import Group
from rich.padding import Padding
from rich.rule import Rule
from rich.spinner import Spinner
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()

_TOOL_ICONS: Dict[str, str] = {
    "read_file": "\U0001f4d6",
    "write_file": "\u270d ",
    "patch_file": "\U0001fa79",
    "bash": "\U0001f4bb",
    "list_files": "\U0001f4c2",
    "search_files": "\U0001f50d",
    "run_tests": "\U0001f9ea",
}
_DEFAULT_ICON = "\u26a1"

_CODE_EXTS: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".md": "markdown",
}


def show_main_menu(nvidia_ok: bool, ollama_ok: bool, local_ok: bool) -> None:
    """Render the interactive main menu."""
    status = Text()
    status.append("NVIDIA key: ", style="dim")
    status.append("set" if nvidia_ok else "missing", style="green" if nvidia_ok else "red")
    status.append("  ·  Ollama: ", style="dim")
    status.append("detected" if ollama_ok else "not found", style="green" if ollama_ok else "red")
    status.append("  ·  Local GGUF: ", style="dim")
    status.append("ready" if local_ok else "not installed", style="green" if local_ok else "red")

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
            Text("  SIHA", style="bold bright_white"),
            Text(""),
            status,
            Text(""),
            table,
            Text(""),
            Text("  Type a number to choose, or use subcommands directly:", style="dim"),
            Text("    siha chat | siha portal | siha bench | siha improve | siha init-db", style="dim"),
        ),
        title="[bold bright_white]SIHA Main Menu[/bold bright_white]",
        border_style="bright_white",
    ))


def prompt_provider_choice() -> str:
    """Ask the user which local provider they want."""
    console.print("")
    console.print("  [bold]Local model options:[/bold]")
    console.print("    a) Auto-detect (Ollama -> in-process tiny model)")
    console.print("    b) Use Ollama")
    console.print("    c) Use in-process tiny model (auto-download)")
    choice = console.input("  [bold cyan]Choice:[/bold cyan] ").strip().lower()
    if choice == "b":
        return "ollama"
    if choice == "c":
        return "local"
    return "auto"


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
        header.append("  SIHA", style="bold bright_white")
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
                label = "Reasoning" if is_reasoning else "Thinking"
                return Panel(
                    Text(tail, style=style, overflow="fold"),
                    title=f"[bold cyan]{label}[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 1),
                )
            return Panel(
                Spinner("dots", text="  Waiting for model...", style="cyan"),
                title="[bold cyan]Thinking[/bold cyan]",
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
                snippet = code_content[:700] + ("  ..." if len(code_content) > 700 else "")
                code_block = Syntax(
                    snippet, lang, theme="monokai",
                    line_numbers=False, word_wrap=True,
                )
                path_hint = Text()
                if file_path:
                    path_hint.append(f"  -> {file_path}", style="dim yellow")
                return Panel(
                    Group(tool_label, path_hint, Padding(code_block, (1, 0, 0, 2))),
                    title="[bold yellow]Calling Tool[/bold yellow]",
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
                    title="[bold yellow]Calling Tool[/bold yellow]",
                    border_style="yellow",
                    padding=(0, 1),
                )

            return Panel(
                tool_label,
                title="[bold yellow]Calling Tool[/bold yellow]",
                border_style="yellow",
                padding=(0, 1),
            )

        if self.status == "done":
            return Panel(
                Text("  Complete.", style="bold green"),
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
            t.append("  OK  " if success else "  FAIL  ", style="bold green" if success else "bold red")
            t.append(f"{icon}  ", style="dim")
            t.append(label, style="white")
            if duration_ms:
                t.append(f"  ·  {duration_ms}ms", style="dim")
            items.append(t)
        return Group(Rule("[dim]Activity[/dim]", style="bright_black"), *items, Text(""))
