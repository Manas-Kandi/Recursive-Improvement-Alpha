"""Configuration management using pydantic-settings"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # API Keys
    nvidia_api_key: str = ""
    search_api_key: str = ""
    portal_dev_token: str = "dev"
    
    # Model Configuration
    agent_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    meta_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    discovery_model: str = "moonshotai/kimi-k2.6"
    
    # NVIDIA API endpoint
    nvidia_api_base: str = "https://integrate.api.nvidia.com/v1"
    
    # Execution limits
    timeout_s: int = 120
    max_output_bytes: int = 100000
    step_budget: int = 50
    max_retries: int = 3
    
    # Sandbox
    sandbox_default: Literal["local", "docker"] = "local"
    
    # Self-improvement
    require_human_approval: bool = False
    improve_interval_s: int = 300
    benchmark_promote_threshold: float = 0.05
    
    # LLM parameters
    temperature: float = 0.7
    benchmark_temperature: float = 0.1
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


settings = Settings()
