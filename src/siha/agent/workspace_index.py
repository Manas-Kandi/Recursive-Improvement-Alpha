"""Workspace index — compact, deterministic snapshot of the sandbox filesystem.

Replaces the "last created folder" heuristic with an actual picture of the
workspace. The index is injected into the system prompt and the planner
context so path references are grounded in reality rather than guessed.
"""

from pathlib import Path
from typing import List, Optional

# Directories that add noise without information.
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}

MAX_ENTRIES = 50
MAX_DEPTH = 3


def build_workspace_index(
    root: Optional[Path],
    max_entries: int = MAX_ENTRIES,
    max_depth: int = MAX_DEPTH,
) -> str:
    """Render a compact file-tree summary of the workspace.

    Returns an empty string when the workspace is missing or empty so callers
    can skip injection entirely.
    """
    if root is None:
        return ""
    root = Path(root)
    if not root.is_dir():
        return ""

    lines: List[str] = []
    truncated = False

    def _walk(directory: Path, depth: int, prefix: str) -> None:
        nonlocal truncated
        if depth > max_depth or truncated:
            return
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except OSError:
            return
        for entry in entries:
            if entry.name in _SKIP_DIRS or entry.name.startswith("__siha"):
                continue
            if len(lines) >= max_entries:
                truncated = True
                return
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                _walk(entry, depth + 1, prefix + "  ")
            else:
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                lines.append(f"{prefix}{entry.name} ({size}B)")

    _walk(root, 1, "")

    if not lines:
        return ""

    body = "\n".join(lines)
    if truncated:
        body += "\n... (truncated)"
    return f"Workspace contents:\n{body}"
