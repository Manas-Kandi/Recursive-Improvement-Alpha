"""Dynamic tool: executes DB-stored python_code tools inside the sandbox.

A dynamic tool's stored code must define a top-level function named ``run`` that
accepts keyword arguments and returns a JSON-serializable value (or a string).
The code is executed inside the sandbox for isolation; arguments are passed via
a JSON file and the return value is captured via sentinel markers on stdout.
"""

import json
from typing import Any, Dict, Optional
from siha.tools.base import Tool, ToolResult
from siha.sandbox.base import Sandbox
from siha.sandbox.local import LocalSandbox


_RESULT_START = "__SIHA_RESULT_START__"
_RESULT_END = "__SIHA_RESULT_END__"


class DynamicTool(Tool):
    """A tool whose implementation is Python code loaded from the database."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        code: str,
        sandbox: Optional[Sandbox] = None,
    ):
        self._name = name
        self._description = description
        self._parameters = parameters or {"type": "object", "properties": {}}
        self._code = code
        self._sandbox = sandbox

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    @property
    def sandbox(self) -> Sandbox:
        if self._sandbox is None:
            self._sandbox = LocalSandbox()
        return self._sandbox

    @sandbox.setter
    def sandbox(self, value: Sandbox):
        self._sandbox = value

    def _build_runner(self) -> str:
        return f'''
import json, traceback

{self._code}

def _siha_entry():
    with open("__siha_args.json") as f:
        args = json.load(f)
    return run(**args)

try:
    _out = _siha_entry()
    print("{_RESULT_START}")
    print(json.dumps({{"ok": True, "result": _out}}, default=str))
    print("{_RESULT_END}")
except Exception as e:
    print("{_RESULT_START}")
    print(json.dumps({{"ok": False, "error": str(e), "trace": traceback.format_exc()}}))
    print("{_RESULT_END}")
'''

    def run(self, **kwargs) -> ToolResult:
        files = {
            "__siha_tool.py": self._build_runner(),
            "__siha_args.json": json.dumps(kwargs),
        }
        result = self.sandbox.run("python3 __siha_tool.py", files=files)

        if _RESULT_START in result.stdout and _RESULT_END in result.stdout:
            raw = result.stdout.split(_RESULT_START, 1)[1].split(_RESULT_END, 1)[0].strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"ok": False, "error": "Failed to parse tool output"}

            if payload.get("ok"):
                out = payload.get("result")
                return ToolResult(
                    success=True,
                    output=out if isinstance(out, str) else json.dumps(out),
                    data={"result": out},
                )
            return ToolResult(
                success=False,
                output="",
                error=payload.get("error", "Unknown error"),
                data={"trace": payload.get("trace")},
            )

        return ToolResult(
            success=False,
            output=result.stdout,
            error=result.stderr or "Tool produced no result markers",
            data={"exit_code": result.exit_code},
        )
