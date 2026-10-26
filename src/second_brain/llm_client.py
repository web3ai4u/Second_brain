"""LLM client - Layer A (Generation).

Uses OpenRouter free models with automatic fallback.
If all models fail or no API key, falls back to heuristic.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

FREE_MODELS = [
    "openrouter/free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen3.8-27b:free",
]

MAX_RETRIES_PER_MODEL = 2
RATE_LIMIT_WAIT = 5


@dataclass
class LLMResponse:
    content: str
    model: str
    fallback_used: bool = False


class LLMClient:
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._models = list(FREE_MODELS)
        self._model_stats: dict[str, dict] = {}

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _record_attempt(self, model: str, success: bool) -> None:
        if model not in self._model_stats:
            self._model_stats[model] = {"attempts": 0, "successes": 0}
        self._model_stats[model]["attempts"] += 1
        if success:
            self._model_stats[model]["successes"] += 1

    def _get_best_model(self) -> Optional[str]:
        if not self._models:
            return None
        available = []
        for m in self._models:
            stats = self._model_stats.get(m, {"attempts": 0, "successes": 0})
            if stats["attempts"] == 0:
                available.append((m, 1.0))
            elif stats["successes"] > 0:
                rate = stats["successes"] / stats["attempts"]
                available.append((m, rate))
        if not available:
            return self._models[0] if self._models else None
        available.sort(key=lambda x: x[1], reverse=True)
        return available[0][0]

    def classify(self, text: str, categories: list[str]) -> Optional[LLMResponse]:
        if not self.is_available:
            logger.info("No API key, LLM unavailable")
            return None
        prompt = (
            f"Classify the following text into exactly one category.\n"
            f"Categories: {', '.join(categories)}\n"
            f"Reply with ONLY the category name, nothing else.\n\n"
            f"Text:\n{text[:2000]}"
        )
        tried = []
        best = self._get_best_model()
        order = [best] + [m for m in self._models if m != best] if best else self._models
        for model in order:
            if model in tried:
                continue
            tried.append(model)
            for attempt in range(MAX_RETRIES_PER_MODEL):
                try:
                    resp = self._call_api(model, prompt)
                    if resp:
                        category = resp.strip().lower()
                        if category in [c.lower() for c in categories]:
                            matched = next(c for c in categories if c.lower() == category)
                            self._record_attempt(model, True)
                            return LLMResponse(
                                content=matched,
                                model=model,
                                fallback_used=(model != best),
                            )
                        logger.warning("LLM returned invalid category: %s", resp)
                except RateLimitError:
                    logger.warning("Rate limit for %s, waiting", model)
                    self._record_attempt(model, False)
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                except Exception as e:
                    logger.warning("LLM call failed: %s model=%s", e, model)
                    self._record_attempt(model, False)
                    break
        logger.info("All LLM models failed, fallback to heuristic")
        return None

    def _call_api(self, model: str, prompt: str) -> Optional[str]:
        try:
            import urllib.request
            import urllib.error
            url = "https://openrouter.ai/api/v1/chat/completions"
            body = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 50,
                "temperature": 0.1,
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/web3ai4u/Second_brain",
            })
            req.timeout = 30
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError(f"Rate limited: {model}")
            raise
        except Exception as e:
            raise LLMCallError(f"API error: {e}")


class RateLimitError(Exception):
    pass


class LLMCallError(Exception):
    pass
