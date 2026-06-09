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


def test_persistent_workspace_not_cleaned(tmp_path):
    """Test persistent workspaces keep generated files after cleanup"""
    workspace = tmp_path / "workspace"
    sandbox = LocalSandbox(workspace_dir=workspace)

    result = sandbox.run("echo hello > hello.txt")
    sandbox.cleanup()

    assert result.success == True
    assert workspace.exists()
    assert (workspace / "hello.txt").read_text().strip() == "hello"


def test_persistent_workspace_blocks_file_escape(tmp_path):
    """Test file injection cannot write outside persistent workspace"""
    workspace = tmp_path / "workspace"
    sandbox = LocalSandbox(workspace_dir=workspace)

    with pytest.raises(ValueError):
        sandbox.run("true", files={"../escape.txt": "bad"})


def test_docker_sandbox_blocks_file_escape(tmp_path):
    """Test DockerSandbox file injection cannot write outside temp dir."""
    from siha.sandbox.docker import DockerSandbox

    sandbox = DockerSandbox()
    with pytest.raises(ValueError, match="escapes sandbox workspace"):
        sandbox.resolve_path("../escape.txt")
    sandbox.cleanup()
