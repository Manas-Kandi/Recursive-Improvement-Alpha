"""Tests for sandbox functionality"""

import pytest
from siha.sandbox.local import LocalSandbox, SandboxResult


def test_local_sandbox_basic():
    """Test basic local sandbox execution"""
    sandbox = LocalSandbox()
    
    result = sandbox.run("echo 'hello'")
    
    assert result.success == True
    assert "hello" in result.stdout
    assert result.exit_code == 0


def test_local_sandbox_timeout():
    """Test sandbox timeout"""
    sandbox = LocalSandbox()
    
    result = sandbox.run("sleep 10", timeout=1)
    
    assert result.success == False
    assert result.error == "timeout"


def test_local_sandbox_with_files():
    """Test sandbox with file creation"""
    sandbox = LocalSandbox()
    
    files = {"test.txt": "content"}
    result = sandbox.run("cat test.txt", files=files)
    
    assert result.success == True
    assert "content" in result.stdout


def test_sandbox_cleanup():
    """Test sandbox cleanup"""
    sandbox = LocalSandbox()
    temp_dir = sandbox.temp_dir
    
    sandbox.cleanup()
    
    assert not temp_dir.exists()
