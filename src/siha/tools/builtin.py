"""Built-in tools: run_python, run_shell, read/write_file, list_dir, web_search, browse_web"""

from typing import Dict, Any, Optional
import shlex
from siha.tools.base import Tool, ToolResult
from siha.sandbox.base import Sandbox
from siha.sandbox.local import LocalSandbox


class SandboxTool(Tool):
    """Base class for tools that execute against a shared sandbox.

    The sandbox is injected so that a sequence of tool calls within a single
    task share the same working directory (e.g. write_file then read_file).
    """

    def __init__(self, sandbox: Optional[Sandbox] = None):
        self._sandbox: Optional[Sandbox] = sandbox

    @property
    def sandbox(self) -> Sandbox:
        if self._sandbox is None:
            self._sandbox = LocalSandbox()
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: Sandbox):
        self._sandbox = value

    def resolve_path(self, path: str) -> str:
        resolver = getattr(self.sandbox, "resolve_path", None)
        if callable(resolver):
            return str(resolver(path))
        return path


class RunPythonTool(SandboxTool):
    """Execute Python code in the sandbox"""

    @property
    def name(self) -> str:
        return "run_python"
    
    @property
    def description(self) -> str:
        return "Execute Python code and return the output"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                }
            },
            "required": ["code"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        code = kwargs.get("code", "")
        files = {"script.py": code}
        result = self.sandbox.run("python3 script.py", files=files)
        return ToolResult(
            success=result.success,
            output=result.stdout,
            error=result.stderr if not result.success else None,
            data={"exit_code": result.exit_code}
        )


class RunShellTool(SandboxTool):
    """Execute shell commands in the sandbox"""

    @property
    def name(self) -> str:
        return "run_shell"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return the output"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                }
            },
            "required": ["command"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        result = self.sandbox.run(command)
        return ToolResult(
            success=result.success,
            output=result.stdout,
            error=result.stderr if not result.success else None,
            data={"exit_code": result.exit_code}
        )


class ReadFileTool(SandboxTool):
    """Read file contents"""

    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        try:
            resolved_path = self.resolve_path(path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e), data={"path": path})
        result = self.sandbox.run(f"cat {shlex.quote(resolved_path)}")
        if result.success:
            return ToolResult(
                success=True,
                output=result.stdout,
                data={"path": path}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=result.stderr,
                data={"path": path}
            )


class WriteFileTool(SandboxTool):
    """Write content to a file"""

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        try:
            resolved_path = self.resolve_path(path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e), data={"path": path})
        result = self.sandbox.run(
            f"mkdir -p $(dirname {shlex.quote(resolved_path)}) && cp __siha_write__ {shlex.quote(resolved_path)}",
            files={"__siha_write__": content},
        )
        if result.success:
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} bytes to {path}",
                data={"path": path, "content_length": len(content)}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=result.stderr,
                data={"path": path}
            )


class ListDirTool(SandboxTool):
    """List directory contents"""

    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list"
                }
            },
            "required": ["path"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        try:
            resolved_path = self.resolve_path(path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e), data={"path": path})
        result = self.sandbox.run(f"ls -la {shlex.quote(resolved_path)}")
        if result.success:
            return ToolResult(
                success=True,
                output=result.stdout,
                data={"path": path}
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=result.stderr,
                data={"path": path}
            )


class WebSearchTool(Tool):
    """Search the web for information"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web for information"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                }
            },
            "required": ["query"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        from siha.tools.search import get_search_provider

        query = kwargs.get("query", "")
        max_results = int(kwargs.get("max_results", 5))

        try:
            results = get_search_provider().search(query, max_results=max_results)
            lines = [
                f"- {r.get('title', '')}\n  {r.get('url', '')}\n  {r.get('content', '')[:300]}"
                for r in results
            ]
            output = "\n".join(lines) if lines else "No results found."
            return ToolResult(
                success=True,
                output=output,
                data={"query": query, "results": results},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Web search failed: {e}",
                data={"query": query},
            )


class BrowseWebTool(Tool):
    """Browse and read web pages"""
    
    @property
    def name(self) -> str:
        return "browse_web"
    
    @property
    def description(self) -> str:
        return "Fetch and read a web page"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch"
                }
            },
            "required": ["url"]
        }
    
    def run(self, **kwargs) -> ToolResult:
        import re
        import html
        import httpx
        from siha.config import settings

        url = kwargs.get("url", "")
        max_chars = int(kwargs.get("max_chars", settings.max_output_bytes))

        try:
            resp = httpx.get(
                url,
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "SIHA-Agent/0.1 (+https://example.com)"},
            )
            resp.raise_for_status()
            text = resp.text
            # Strip scripts/styles, then tags, to produce readable text.
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            return ToolResult(
                success=True,
                output=text[:max_chars],
                data={"url": str(resp.url), "status_code": resp.status_code},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to fetch {url}: {e}",
                data={"url": url},
            )


# Tool classes available as built-ins. The registry instantiates these so a
# fresh, sandbox-bound set can be created per task.
BUILTIN_TOOL_CLASSES = [
    RunPythonTool,
    RunShellTool,
    ReadFileTool,
    WriteFileTool,
    ListDirTool,
    WebSearchTool,
    BrowseWebTool,
]

# Default shared instances (used when no per-task binding is required).
BUILTIN_TOOLS = [cls() for cls in BUILTIN_TOOL_CLASSES]
