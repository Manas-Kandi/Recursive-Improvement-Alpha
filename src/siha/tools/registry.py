"""Tool registry - merges builtin and dynamically loaded DB tools"""

from typing import Dict, List, Optional
from siha.tools.base import Tool
from siha.tools.builtin import BUILTIN_TOOL_CLASSES
from siha.tools.dynamic import DynamicTool
from siha.sandbox.base import Sandbox
from siha.db import get_session
from siha.models import Tool as ToolModel, ToolStatus, ToolKind


class ToolRegistry:
    """Registry for all available tools (builtin + DB python_code tools)."""

    def __init__(self):
        self._builtin_tools: Dict[str, Tool] = {}
        self._db_tools: Dict[str, Tool] = {}
        self._sandbox: Optional[Sandbox] = None
        self.reload()

    def reload(self):
        """(Re)instantiate builtin tools and load active DB tools."""
        self._builtin_tools = {cls().name: cls() for cls in BUILTIN_TOOL_CLASSES}
        self._db_tools = {}
        self._load_db_tools()
        if self._sandbox is not None:
            self.set_sandbox(self._sandbox)

    def _load_db_tools(self):
        """Load active python_code tools from the database as DynamicTools."""
        with get_session() as session:
            tools = session.query(ToolModel).filter(
                ToolModel.status == ToolStatus.active,
                ToolModel.implementation_kind == ToolKind.python_code,
            ).all()

            for tool_model in tools:
                if not tool_model.code:
                    continue
                self._db_tools[tool_model.name] = DynamicTool(
                    name=tool_model.name,
                    description=tool_model.description,
                    parameters=tool_model.json_schema,
                    code=tool_model.code,
                )

    def set_sandbox(self, sandbox: Sandbox):
        """Bind a shared sandbox to all sandbox-aware tools."""
        self._sandbox = sandbox
        for tool in list(self._builtin_tools.values()) + list(self._db_tools.values()):
            if hasattr(tool, "sandbox"):
                try:
                    tool.sandbox = sandbox
                except AttributeError:
                    pass

    def get_tool(self, name: str) -> Tool:
        """Get a tool by name"""
        if name in self._builtin_tools:
            return self._builtin_tools[name]
        if name in self._db_tools:
            return self._db_tools[name]
        raise KeyError(f"Tool not found: {name}")

    def list_tools(self) -> List[str]:
        """List all available tool names"""
        return list(self._builtin_tools.keys()) + list(self._db_tools.keys())

    def to_openai_tools(self) -> List[Dict]:
        """Convert all tools to OpenAI tool-calling format"""
        tools = []
        for tool in self._builtin_tools.values():
            tools.append(tool.to_openai_format())
        for tool in self._db_tools.values():
            tools.append(tool.to_openai_format())
        return tools


# Global registry instance
registry = ToolRegistry()
