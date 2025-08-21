"""LLM client abstraction supporting multiple providers."""

import asyncio
import json
from typing import AsyncGenerator, Dict, List, Any, Optional
import httpx

from .config import get_settings
from .utils import log_structured


settings = get_settings()


class LLMClient:
    """Abstract base for LLM clients."""
    
    def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.2, 
        max_tokens: int = 800
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion responses."""
        raise NotImplementedError


class MistralClient(LLMClient):
    """Mistral API client."""
    
    def __init__(self):
        self.api_key = settings.mistral_api_key
        self.model = settings.mistral_model
        self.base_url = settings.mistral_base_url or "https://api.mistral.ai"
        
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY environment variable is required")
    
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.2, 
        max_tokens: int = 800
    ) -> AsyncGenerator[str, None]:
        """Stream responses from Mistral API."""
        
        use_model = model or self.model
        
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            
                            if data and data.strip() == "[DONE]":
                                break
                                
                            try:
                                chunk = json.loads(data)
                                if chunk.get("choices") and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue  # Skip malformed JSON
                                
            except httpx.HTTPStatusError as e:
                log_structured("mistral_api_error", {
                    "status_code": e.response.status_code,
                    "error": str(e)
                })
                raise Exception(f"Mistral API error: {e.response.status_code}")
            except Exception as e:
                log_structured("mistral_client_error", {"error": str(e)})
                raise


class OpenAICompatibleClient(LLMClient):
    """OpenAI-compatible API client (vLLM, etc.)."""
    
    def __init__(self):
        self.base_url = settings.vllm_base_url
        self.api_key = settings.vllm_api_key or "dummy-key"  # Some endpoints don't need real keys
        self.model = settings.vllm_model
        
        if not self.base_url:
            raise ValueError("VLLM_BASE_URL environment variable is required for OpenAI-compatible provider")
    
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.2, 
        max_tokens: int = 800
    ) -> AsyncGenerator[str, None]:
        """Stream responses from OpenAI-compatible API."""
        
        use_model = model or self.model
        
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{(self.base_url or '').rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            
                            if data and data.strip() == "[DONE]":
                                break
                                
                            try:
                                chunk = json.loads(data)
                                if chunk.get("choices") and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
                                
            except httpx.HTTPStatusError as e:
                log_structured("openai_compatible_api_error", {
                    "status_code": e.response.status_code,
                    "error": str(e)
                })
                raise Exception(f"OpenAI-compatible API error: {e.response.status_code}")
            except Exception as e:
                log_structured("openai_compatible_client_error", {"error": str(e)})
                raise


def get_llm_client() -> LLMClient:
    """Get LLM client based on configured provider."""
    
    if settings.llm_provider == "mistral":
        return MistralClient()
    elif settings.llm_provider == "openai_compatible":
        return OpenAICompatibleClient()
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


# Test client connectivity
async def test_llm_connectivity(client: LLMClient) -> Dict[str, Any]:
    """Test LLM client connectivity."""
    
    try:
        test_messages = [
            {"role": "user", "content": "Respond with exactly 'TEST_OK' if you can process this message."}
        ]
        
        response_chunks = []
        async for chunk in client.chat(test_messages, max_tokens=10):
            response_chunks.append(chunk)
            
        response_text = "".join(response_chunks)
        
        return {
            "status": "connected",
            "response": response_text,
            "provider": settings.llm_provider
        }
        
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "provider": settings.llm_provider
        }
