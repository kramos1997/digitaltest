"""Dependency injection for FastAPI routes."""

import httpx
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings
from .llm_client import get_llm_client as _get_llm_client


def get_search_client():
    """Get HTTP client for search requests."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={
            "User-Agent": "ClarityDesk-Research/1.0 (GDPR-compliant research platform)"
        }
    )


def get_llm_client():
    """Get LLM client based on configured provider."""
    return _get_llm_client()


def get_rate_limiter():
    """Get rate limiter instance."""
    return Limiter(key_func=get_remote_address)
