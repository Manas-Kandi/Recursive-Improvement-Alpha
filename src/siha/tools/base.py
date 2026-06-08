"""Tool abstract base class and result types"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result of a tool execution"""
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class Tool(ABC):
    """Abstract base class for all tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for the LLM"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON Schema for tool parameters"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool"""
        pass
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI tool calling format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
