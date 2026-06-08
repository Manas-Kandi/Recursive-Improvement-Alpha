"""Local subprocess sandbox implementation"""

import subprocess
import tempfile
import shutil
import time
from pathlib import Path
from typing import Dict, Optional
from siha.sandbox.base import Sandbox, SandboxResult
from siha.config import settings


class LocalSandbox(Sandbox):
    """Sandbox using temporary directories and subprocess"""
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.temp_dir: Optional[Path] = None
        self._persistent = workspace_dir is not None
        if workspace_dir is not None:
            self.temp_dir = Path(workspace_dir).expanduser().resolve()
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._create_temp_dir()
    
    def _create_temp_dir(self):
        """Create a temporary directory for the sandbox"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="siha_sandbox_"))
    
    def run(
        self,
        command: str,
        files: Optional[Dict[str, str]] = None,
        timeout: int = 120
    ) -> SandboxResult:
        """Run a command in the sandbox"""
        if not self.temp_dir:
            self._create_temp_dir()
        
        # Write files if provided
        if files:
            for file_path, content in files.items():
                full_path = self.resolve_path(file_path)
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            stdout = result.stdout[: settings.max_output_bytes]
            stderr = result.stderr[: settings.max_output_bytes]
            return SandboxResult(
                success=result.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=result.returncode,
                duration_ms=duration_ms
            )
            
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
                error="timeout"
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    def cleanup(self):
        """Clean up the temporary directory"""
        if not self._persistent and self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def resolve_path(self, file_path: str) -> Path:
        """Resolve a file path and ensure it stays inside the sandbox root."""
        if not self.temp_dir:
            self._create_temp_dir()
        root = self.temp_dir.resolve()
        resolved = (root / file_path).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Path escapes sandbox workspace: {file_path}")
        return resolved
