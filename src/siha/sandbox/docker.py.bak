"""Docker sandbox implementation.

Runs commands inside an ephemeral, network-isolated container using the local
`docker` CLI. Falls back gracefully with a clear error if Docker is unavailable.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional
from siha.sandbox.base import Sandbox, SandboxResult
from siha.config import settings


class DockerUnavailableError(RuntimeError):
    """Raised when the Docker CLI/daemon is not available."""


class DockerSandbox(Sandbox):
    """Sandbox that executes commands inside an isolated Docker container."""

    def __init__(self, image: str = "python:3.11-slim", network: str = "none"):
        self.image = image
        self.network = network
        self.temp_dir: Optional[Path] = None
        self._create_temp_dir()

    @staticmethod
    def is_available() -> bool:
        """Return True if the docker CLI and daemon are reachable."""
        if shutil.which("docker") is None:
            return False
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _create_temp_dir(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="siha_docker_"))

    def run(
        self,
        command: str,
        files: Optional[Dict[str, str]] = None,
        timeout: int = 120,
    ) -> SandboxResult:
        if not self.temp_dir:
            self._create_temp_dir()

        if not self.is_available():
            return SandboxResult(
                success=False,
                stdout="",
                stderr="Docker is not available on this host.",
                exit_code=-1,
                duration_ms=0,
                error="docker_unavailable",
            )

        if files:
            for file_path, content in files.items():
                full_path = self.temp_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", self.network,
            "--memory", "512m",
            "--cpus", "1",
            "-v", f"{self.temp_dir}:/workspace",
            "-w", "/workspace",
            self.image,
            "sh", "-c", command,
        ]

        start_time = time.time()
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout[: settings.max_output_bytes],
                stderr=result.stderr[: settings.max_output_bytes],
                exit_code=result.returncode,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
                error="timeout",
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
                error=str(e),
            )

    def cleanup(self):
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
