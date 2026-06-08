"""LLM Provider Protocol + NVIDIA Client"""

import time
from abc import ABC, abstractmethod
from typing import Iterator, Optional, Dict, Any, List

from openai import OpenAI
from openai import APIConnectionError, APIStatusError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from siha.config import settings


class LLMProvider(ABC):
    """Abstract base for any LLM backend."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self.temperature = settings.temperature

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> ChatCompletion:
        """Non-streaming chat completion."""
        ...

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Iterator[ChatCompletionChunk]:
        """Streaming chat completion."""
        ...

    def extract_reasoning(self, chunk: ChatCompletionChunk) -> Optional[str]:
        """Extract reasoning_content from streaming chunks if available."""
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                return delta.reasoning_content
        return None


class NvidiaClient(LLMProvider):
    """Wrapper for NVIDIA Integrate API (OpenAI-compatible)."""

    def __init__(self, model: Optional[str] = None):
        super().__init__(model=model or settings.agent_model)
        if not settings.nvidia_api_key:
            raise RuntimeError("NVIDIA_API_KEY is required for the nvidia provider.")
        self.client = OpenAI(
            base_url=settings.nvidia_api_base,
            api_key=settings.nvidia_api_key
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> ChatCompletion:
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if tools:
            params["tools"] = tools
        if max_tokens:
            params["max_tokens"] = max_tokens
        if stream:
            params["stream"] = True
        return self._create_with_retry(params)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Iterator[ChatCompletionChunk]:
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
        return self._create_with_retry(params)

    def _create_with_retry(self, params: Dict[str, Any]):
        last_error = None
        for attempt in range(settings.max_retries + 1):
            try:
                return self.client.chat.completions.create(**params)
            except (RateLimitError, APIConnectionError, APIStatusError) as e:
                last_error = e
                status_code = getattr(e, "status_code", None)
                if status_code is not None and status_code < 500 and status_code != 429:
                    raise
                if attempt >= settings.max_retries:
                    raise
                time.sleep(min(2 ** attempt, 8))
        raise last_error
