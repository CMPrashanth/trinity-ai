"""Groq Cloud LLM client for testing - NOT for production use.

WhiteRabbitNeo remains the production model. Groq is only used when:
1. Ollama is unavailable (e.g., no GPU, insufficient memory)
2. Running integration tests
3. Development/debugging

To use: Set GROQ_API_KEY environment variable with free key from https://console.groq.com
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

import httpx

from ..config import settings


class GroqClient:
    """Async client for Groq Cloud API - testing fallback only."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.GROQ_API_KEY
        # Use Llama-3.1-8B on Groq (same architecture as WhiteRabbitNeo)
        self._model = model or "llama-3.1-8b-instant"
        self._base_url = "https://api.groq.com/openai/v1"
        
        if not self._api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Get free key from https://console.groq.com"
            )

    async def generate_json(
        self,
        prompt: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate JSON response via Groq API."""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": options.get("temperature", 0.7) if options else 0.7,
                    "max_tokens": options.get("num_predict", 2048) if options else 2048,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Groq response was not valid JSON: {content[:200]}") from exc

    async def generate_text(
        self,
        prompt: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate text response via Groq API."""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": options.get("temperature", 0.7) if options else 0.7,
                    "max_tokens": options.get("num_predict", 2048) if options else 2048,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        return data["choices"][0]["message"]["content"]
