"""NVIDIA LLM client with streaming and reasoning support"""

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from typing import Iterator, Optional, Dict, Any, List
from siha.config import settings


class NvidiaClient:
    """Wrapper for NVIDIA Integrate API (OpenAI-compatible)"""
    
    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.agent_model
        self.temperature = settings.temperature
        self.client = OpenAI(
            base_url=settings.nvidia_api_base,
            api_key=settings.nvidia_api_key
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> ChatCompletion:
        """Non-streaming chat completion"""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        
        if tools:
            params["tools"] = tools
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        return self.client.chat.completions.create(**params)
    
    def stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Iterator[ChatCompletionChunk]:
        """Streaming chat completion with reasoning content capture"""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }
        
        if tools:
            params["tools"] = tools
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        return self.client.chat.completions.create(**params)
    
    def extract_reasoning(self, chunk: ChatCompletionChunk) -> Optional[str]:
        """Extract reasoning_content from streaming chunks if available"""
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            # Some models expose reasoning in a special field
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                return delta.reasoning_content
        return None
