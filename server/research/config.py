"""Configuration management for the research system."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class ResearchSettings(BaseSettings):
    """Research system configuration."""
    
    # Search API Configuration
    google_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None
    serper_api_key: Optional[str] = None
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Research Configuration
    max_search_results: int = 15
    max_sources_per_query: int = 20
    request_timeout: int = 30
    scraping_delay: float = 1.0
    max_content_length: int = 50000
    
    # Rate Limiting
    searches_per_minute: int = 60
    scrapes_per_minute: int = 120
    
    # Quality Thresholds
    min_content_length: int = 100
    min_relevance_score: float = 0.3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = ResearchSettings()