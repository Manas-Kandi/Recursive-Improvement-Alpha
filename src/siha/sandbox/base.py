"""Sandbox abstract base class"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class SandboxResult(BaseModel):
    """Result of sandbox execution"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    error: Optional[str] = None


class Sandbox(ABC):
    """Abstract base class for sandbox implementations"""
    
    @abstractmethod
    def run(
        self,
        command: str,
        files: Optional[Dict[str, str]] = None,
        timeout: int = 120
    ) -> SandboxResult:
        """Run a command in the sandbox"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up sandbox resources"""
        pass
