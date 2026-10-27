from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str


class LLMClient:
    """Minimal, provider-agnostic LLM client with OpenRouter fallback."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._base_url = base_url or os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self._model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b")
        self._provider_name = "openrouter"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _record_attempt(self, model: str, success: bool) -> None:
        logger.info("LLM attempt model=%s success=%s", model, success)

    def _call_openrouter(self, prompt: str, model: str) -> str:
        if not self._api_key:
            raise RuntimeError("OpenRouter API key is not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/web3ai4u/Second_brain",
            "X-Title": "Second Brain",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        response = requests.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def classify(self, text: str, allowed_categories: list[str]) -> LLMResponse:
        prompt = f"""
You are a knowledge-product analyst. Classify the user's content into ONE category from the list below.
Return only a valid JSON object with keys:
- category
- confidence
- reason
- product_ideas
- course_ideas
- agent_ideas
- monetization_ideas

Allowed categories:
{allowed_categories}

Source content:
{text[:12000]}
"""
        content = self._call_openrouter(prompt, self._model)
        self._record_attempt(self._model, True)
        return LLMResponse(content=content, model=self._model, provider=self._provider_name)

    def analyze_for_products(self, text: str) -> LLMResponse:
        prompt = f"""
Analyze this material for product and business potential.
Return only valid JSON with keys:
- topic
- audience
- value_proposition
- course_ideas
- agent_ideas
- app_ideas
- monetization_ideas
- commercial_potential
- confidence

Material:
{text[:15000]}
"""
        content = self._call_openrouter(prompt, self._model)
        self._record_attempt(self._model, True)
        return LLMResponse(content=content, model=self._model, provider=self._provider_name)
