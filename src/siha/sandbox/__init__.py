"""Sandbox execution environments"""

from pathlib import Path
from typing import Optional
from siha.sandbox.base import Sandbox, SandboxResult
from siha.sandbox.local import LocalSandbox


def create_sandbox(mode: str = "local", workspace_dir: Optional[Path] = None) -> Sandbox:
    """Factory that returns a sandbox for the requested mode.

    Falls back to the local sandbox if Docker is requested but unavailable.
    """
    if mode == "docker":
        from siha.sandbox.docker import DockerSandbox

        if workspace_dir is not None:
            return LocalSandbox(workspace_dir=workspace_dir)
        if DockerSandbox.is_available():
            return DockerSandbox()
        # Graceful fallback so tasks still run on hosts without Docker.
        return LocalSandbox()
    return LocalSandbox(workspace_dir=workspace_dir)


__all__ = ["Sandbox", "SandboxResult", "LocalSandbox", "create_sandbox"]
