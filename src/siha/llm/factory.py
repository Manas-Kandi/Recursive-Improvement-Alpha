"""Auto-detecting LLM client factory."""

from typing import Optional

from siha.config import settings
from siha.llm.client import LLMProvider, NvidiaClient
from siha.llm.ollama import OllamaClient, is_ollama_reachable
from siha.llm.local_gguf import LocalGGUFClient, is_llama_cpp_available


def detect_provider() -> str:
    """Heuristic to pick the best available provider."""
    if settings.nvidia_api_key:
        return "nvidia"
    if is_ollama_reachable():
        return "ollama"
    if is_llama_cpp_available():
        return "local"
    # Fallback: if nothing is available, default to nvidia so the user gets a clear error
    return "nvidia"


def create_llm_client(
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> LLMProvider:
    """Create the appropriate LLM client based on settings or overrides.

    Args:
        model: Optional model override.
        provider: Explicit provider name. If None, uses ``settings.llm_provider``.
    """
    prov = (provider or settings.llm_provider).lower()
    if prov == "auto":
        prov = detect_provider()

    if prov == "nvidia":
        return NvidiaClient(model=model)
    if prov == "ollama":
        return OllamaClient(model=model)
    if prov == "local":
        return LocalGGUFClient(model=model)

    raise ValueError(f"Unknown LLM provider: {prov}")
