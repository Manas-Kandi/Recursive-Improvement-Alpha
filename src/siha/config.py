"""Configuration management using pydantic-settings"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # API Keys
    nvidia_api_key: str = ""
    search_api_key: str = ""
    search_provider: Literal["auto", "tavily", "brave", "duckduckgo"] = "auto"
    portal_dev_token: str = "dev"

    # Provider selection
    llm_provider: Literal["auto", "nvidia", "ollama", "local"] = "auto"

    # Model Configuration
    agent_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    meta_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    discovery_model: str = "moonshotai/kimi-k2.6"

    # NVIDIA API endpoint
    nvidia_api_base: str = "https://integrate.api.nvidia.com/v1"

    # Ollama settings
    ollama_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5-coder:0.5b"

    # Local (in-process) GGUF settings
    local_model_repo: str = "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF"
    local_model_file: str = "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf"
    local_model_cache_dir: str = "~/.cache/siha/models"
    local_model_context_size: int = 4096
    local_model_n_threads: int = 0  # 0 = auto

    # Execution limits
    timeout_s: int = 120
    max_output_bytes: int = 100000
    step_budget: int = 50
    max_retries: int = 3

    # Sandbox
    sandbox_default: Literal["local", "docker"] = "local"

    # Self-improvement
    require_human_approval: bool = True
    improve_interval_s: int = 300
    benchmark_promote_threshold: float = 0.05
    # Number of repetitions per benchmark when scoring a harness version.
    # Scores are averaged so a single flaky run cannot flip a promotion.
    benchmark_runs: int = 3
    # Reuse previously recorded scores for a harness version when available.
    benchmark_cache: bool = True
    # Upper bound on auto-generated benchmarks so the suite stays tractable.
    max_auto_benchmarks: int = 50
    # Graduated trust for synthesized templates: a template stays in
    # probation (planner shadow-confirms each match) until it accumulates
    # this many confirmed successes.
    template_probation_runs: int = 3
    # Synthesized templates whose failures reach this count (and exceed
    # their successes) are automatically archived.
    template_failure_archive_threshold: int = 3

    # LLM parameters
    temperature: float = 0.7
    benchmark_temperature: float = 0.1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


settings = Settings()
