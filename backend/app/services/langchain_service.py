"""LangChain wrapper for local Ollama-powered security reasoning."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..config import settings

try:
    from langchain_ollama import ChatOllama
except ImportError:  # pragma: no cover - guarded for partial installs
    ChatOllama = None


class LangChainService:
    """Utility class for structured LLM prompts used by Trinity workflows."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        if ChatOllama is None:
            raise RuntimeError("langchain-ollama is not installed")

        self.model = model or settings.LLM_MODEL_ID
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=0.1,
        )

    async def summarize_remediation(self, vulnerabilities: List[Dict[str, Any]]) -> str:
        """Generate a concise remediation strategy for findings."""
        if not vulnerabilities:
            return "No vulnerabilities detected."

        prompt = (
            "You are a senior penetration testing advisor. "
            "Given vulnerabilities, provide prioritized remediation steps in 4-8 bullet points. "
            "Be specific and actionable.\n\n"
            f"Vulnerabilities JSON:\n{json.dumps(vulnerabilities)[:12000]}"
        )
        response = await self.llm.ainvoke(prompt)
        return getattr(response, "content", str(response)).strip()

    async def plan_adjustments(
        self,
        target: str,
        scan_profile: str,
        existing_reasoning: str,
    ) -> str:
        """Add optional LangChain-generated plan guidance to planner reasoning."""
        prompt = (
            "You are assisting an autonomous pentest planner. "
            "Return a short paragraph with improvements for safe and legal recon. "
            "Do not include destructive or out-of-scope guidance.\n\n"
            f"Target: {target}\n"
            f"Profile: {scan_profile}\n"
            f"Existing plan reasoning: {existing_reasoning}"
        )
        response = await self.llm.ainvoke(prompt)
        return getattr(response, "content", str(response)).strip()
