"""Application configuration using Pydantic settings."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # SearXNG Configuration
    searx_url: str = "https://searx.be"  # Default public instance
    
    # GDPR and Privacy
    gdpr_mode: bool = False
    
    # LLM Configuration
    llm_provider: str = "mistral"  # "mistral" or "openai_compatible"
    
    # Mistral Configuration
    mistral_api_key: Optional[str] = None
    mistral_model: str = "mistral-small"
    mistral_base_url: Optional[str] = None
    
    # OpenAI Compatible Configuration  
    vllm_base_url: Optional[str] = None
    vllm_api_key: Optional[str] = None
    vllm_model: str = "mistral-7b-instruct"
    
    # Feature Flags
    enable_rerank: bool = False
    
    # Rate Limiting
    rate_limit_per_minute: int = 10
    
    # Logging
    log_level: str = "INFO"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
