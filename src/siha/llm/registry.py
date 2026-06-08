"""Model catalog and per-role model resolution"""

from typing import Dict, Optional
from siha.config import settings


# Available models in NVIDIA catalog
MODEL_CATALOG = {
    "nvidia/nemotron-3-ultra-550b-a55b": {
        "supports_reasoning": True,
        "supports_streaming": True,
        "description": "High-reasoning model with reasoning_content support"
    },
    "moonshotai/kimi-k2.6": {
        "supports_reasoning": False,
        "supports_streaming": True,
        "description": "General purpose model"
    },
    "google/gemma-3n-e2b-it": {
        "supports_reasoning": False,
        "supports_streaming": True,
        "description": "Instruction-tuned Gemma model"
    },
    "qwen2.5-coder:0.5b": {
        "supports_reasoning": False,
        "supports_streaming": True,
        "description": "Tiny Ollama coding model (~0.5B params)"
    },
    "phi4-mini": {
        "supports_reasoning": False,
        "supports_streaming": True,
        "description": "Tiny Ollama coding model (~3.8B params)"
    },
    "local-gguf": {
        "supports_reasoning": False,
        "supports_streaming": True,
        "description": "In-process tiny GGUF (auto-downloaded)"
    },
}


def get_model_for_role(role: str) -> str:
    """Get the appropriate model for a given role"""
    role_map = {
        "agent": settings.agent_model,
        "meta": settings.meta_model,
        "discovery": settings.discovery_model,
    }
    return role_map.get(role, settings.agent_model)


def validate_model(model_name: str) -> bool:
    """Check if a model is in the catalog"""
    return model_name in MODEL_CATALOG
