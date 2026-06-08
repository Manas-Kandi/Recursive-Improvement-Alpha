"""Sandbox execution environments"""

from pathlib import Path
from typing import Optional
from siha.sandbox.base import Sandbox, SandboxResult
from siha.sandbox.local import LocalSandbox


def create_sandbox(mode: str = "local", workspace_dir: Optional[Path] = None) -> Sandbox:
    """Factory that returns a sandbox for the requested mode.

    Raises RuntimeError if Docker is requested but unavailable.
    """
    if mode == "docker":
        from siha.sandbox.docker import DockerSandbox

        if not DockerSandbox.is_available():
            raise RuntimeError(
                "Docker sandbox requested but Docker is not available on this host."
            )
        return DockerSandbox()
    return LocalSandbox(workspace_dir=workspace_dir)


__all__ = ["Sandbox", "SandboxResult", "LocalSandbox", "create_sandbox"]
