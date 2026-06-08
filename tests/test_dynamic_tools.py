"""Tests for dynamic tools, shared sandbox, and the sandbox factory."""

import pytest
from siha.sandbox import create_sandbox, LocalSandbox
from siha.tools.builtin import WriteFileTool, ReadFileTool
from siha.tools.dynamic import DynamicTool


def test_sandbox_factory_local():
    sandbox = create_sandbox("local")
    assert isinstance(sandbox, LocalSandbox)


def test_docker_raises_when_unavailable():
    # On hosts without Docker, the factory must raise a clear error.
    with pytest.raises(RuntimeError, match="Docker is not available"):
        create_sandbox("docker")


def test_shared_sandbox_write_then_read():
    sandbox = LocalSandbox()
    writer = WriteFileTool(sandbox=sandbox)
    reader = ReadFileTool(sandbox=sandbox)

    # Content with quotes/newlines must round-trip intact.
    content = "line1\nline2 with 'quotes' and \"double\""
    write_result = writer.run(path="notes.txt", content=content)
    assert write_result.success

    read_result = reader.run(path="notes.txt")
    assert read_result.success
    assert "line1" in read_result.output
    assert "quotes" in read_result.output


def test_write_file_tool_blocks_workspace_escape(tmp_path):
    sandbox = create_sandbox("local", workspace_dir=tmp_path / "workspace")
    writer = WriteFileTool(sandbox=sandbox)

    result = writer.run(path="../escape.txt", content="bad")

    assert not result.success
    assert "escapes sandbox workspace" in result.error
    assert not (tmp_path / "escape.txt").exists()


def test_dynamic_tool_executes_run_function():
    code = "def run(**kwargs):\n    return kwargs.get('a', 0) + kwargs.get('b', 0)\n"
    tool = DynamicTool(
        name="adder",
        description="adds two numbers",
        parameters={"type": "object", "properties": {}},
        code=code,
    )
    result = tool.run(a=2, b=3)
    assert result.success
    assert result.data["result"] == 5


def test_dynamic_tool_reports_error():
    code = "def run(**kwargs):\n    raise ValueError('boom')\n"
    tool = DynamicTool(name="boom", description="fails", parameters={}, code=code)
    result = tool.run()
    assert not result.success
    assert "boom" in (result.error or "")
