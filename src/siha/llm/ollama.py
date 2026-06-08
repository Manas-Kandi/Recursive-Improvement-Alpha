"""Ollama provider — OpenAI-compatible local server."""

from typing import Iterator, List, Dict, Any, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from siha.config import settings
from siha.llm.client import LLMProvider


class OllamaClient(LLMProvider):
    """Wrapper for Ollama's OpenAI-compatible API."""

    def __init__(self, model: Optional[str] = None):
        super().__init__(model=model or settings.ollama_model)
        self.client = OpenAI(
            base_url=settings.ollama_url,
            api_key="ollama"  # Ollama ignores this, but OpenAI client requires it
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
        return self.client.chat.completions.create(**params)

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
        return self.client.chat.completions.create(**params)


def is_ollama_reachable(url: Optional[str] = None) -> bool:
    """Ping the Ollama server to see if it's up."""
    import urllib.request
    import urllib.error

    target = (url or settings.ollama_url).replace("/v1", "/api/tags")
    try:
        with urllib.request.urlopen(target, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, Exception):
        return False
