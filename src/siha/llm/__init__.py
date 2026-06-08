"""LLM client and model registry"""

from siha.llm.client import LLMProvider, NvidiaClient
from siha.llm.factory import create_llm_client, detect_provider
from siha.llm.ollama import OllamaClient, is_ollama_reachable
from siha.llm.local_gguf import LocalGGUFClient, is_llama_cpp_available
from siha.llm.registry import MODEL_CATALOG, get_model_for_role, validate_model

__all__ = [
    "LLMProvider",
    "NvidiaClient",
    "OllamaClient",
    "LocalGGUFClient",
    "create_llm_client",
    "detect_provider",
    "is_ollama_reachable",
    "is_llama_cpp_available",
    "MODEL_CATALOG",
    "get_model_for_role",
    "validate_model",
]
