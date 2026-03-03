"""Thin async wrapper around the Ollama Python client."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

import ollama

from ..config import settings


class OllamaClient:
    """Facilitates structured prompts against the local Ollama runtime."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._host = base_url or settings.OLLAMA_BASE_URL
        self._model = model or settings.LLM_MODEL_ID
        self._client = ollama.Client(host=self._host)

    async def generate_json(
        self,
        prompt: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the JSON-decoded response produced by Ollama."""

        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "format": "json",
        }

        if options:
            payload["options"] = options
        if system:
            payload["system"] = system

        loop = asyncio.get_running_loop()
        response: Dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: self._client.generate(**payload),
        )

        raw = response.get("response") or response.get("message", {}).get("content", "{}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Ollama response was not valid JSON: {raw[:200]}") from exc

    async def generate_text(
        self,
        prompt: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate free-form text when JSON mode is unnecessary."""

        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
        }

        if options:
            payload["options"] = options
        if system:
            payload["system"] = system

        loop = asyncio.get_running_loop()
        response: Dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: self._client.generate(**payload),
        )

        return response.get("response") or response.get("message", {}).get("content", "")
