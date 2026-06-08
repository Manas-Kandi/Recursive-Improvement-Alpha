"""Tests for tool functionality"""

import pytest
from siha.tools.base import ToolResult
from siha.tools.builtin import RunPythonTool, RunShellTool


def test_run_python_tool():
    """Test Python execution tool"""
    tool = RunPythonTool()
    
    result = tool.run(code="print('hello')")
    
    assert result.success == True
    assert "hello" in result.output


def test_run_shell_tool():
    """Test shell execution tool"""
    tool = RunShellTool()
    
    result = tool.run(command="echo 'test'")
    
    assert result.success == True
    assert "test" in result.output


def test_tool_schema():
    """Test tool parameter schema"""
    tool = RunPythonTool()
    
    schema = tool.parameters
    
    assert "type" in schema
    assert "properties" in schema
    assert "code" in schema["properties"]
    assert "required" in schema
