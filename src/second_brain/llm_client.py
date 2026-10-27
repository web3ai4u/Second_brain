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


@dataclass
class BusinessInsight:
    topic: str
    audience: str
    value_proposition: str
    course_ideas: list[str]
    agent_ideas: list[str]
    app_ideas: list[str]
    monetization_ideas: list[str]
    commercial_potential: str
    confidence: float


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

    def analyze_for_products(self, text: str) -> Optional[LLMResponse]:
        if not self.is_available:
            logger.info("No API key, LLM unavailable")
            return None

        prompt = (
            "You are a product analyst. Analyze the source material and return only valid JSON.\n"
            "Required JSON keys: topic, audience, value_proposition, course_ideas, agent_ideas, "
            "app_ideas, monetization_ideas, commercial_potential, confidence.\n"
            "Use arrays for lists. Keep the output valid JSON only, no markdown fences.\n\n"
            f"Source text:\n{text[:15000]}"
        )

        best = self._get_best_model()
        order = [best] + [m for m in self._models if m != best] if best else self._models
        for model in order:
            for attempt in range(MAX_RETRIES_PER_MODEL):
                try:
                    content = self._call_api(model, prompt)
                    if content:
                        return LLMResponse(content=content.strip(), model=model, fallback_used=(model != best))
                except RateLimitError:
                    logger.warning("Rate limit during product analysis for %s, waiting", model)
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                except Exception as e:
                    logger.warning("LLM analysis failed for %s: %s", model, e)
                    break
        logger.info("All LLM models failed for product analysis")
        return None

    def _call_api(self, model: str, prompt: str) -> Optional[str]:
        try:
            import urllib.request
            import urllib.error

            url = "https://openrouter.ai/api/v1/chat/completions"
            body = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.2,
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


class ProductInsightAnalyzer:
    """Convert raw notes into product/course/agent/opportunity ideas."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client

    @staticmethod
    def _safe_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start:end + 1])
            raise ValueError("LLM response was not valid JSON")

    @staticmethod
    def _listify(value, fallback: list[str]) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [value]
        return fallback

    def analyze(self, text: str) -> BusinessInsight:
        fallback = BusinessInsight(
            topic="unknown",
            audience="general knowledge workers",
            value_proposition="The material has useful structure but needs human review before productization.",
            course_ideas=["Turn it into a short workshop or micro-course."],
            agent_ideas=["Build a simple intake agent that extracts and organizes the ideas."],
            app_ideas=["Create a lightweight local note-to-product app."],
            monetization_ideas=["Sell templates, consulting, or a course."],
            commercial_potential="medium",
            confidence=0.35,
        )

        if not self.llm_client or not self.llm_client.is_available:
            return fallback

        try:
            payload = self.llm_client.analyze_for_products(text)
            if payload is None:
                return fallback
            data = self._safe_json(payload.content)
            return BusinessInsight(
                topic=str(data.get("topic", "unknown")),
                audience=str(data.get("audience", "general audience")),
                value_proposition=str(data.get("value_proposition", fallback.value_proposition)),
                course_ideas=self._listify(data.get("course_ideas"), fallback.course_ideas),
                agent_ideas=self._listify(data.get("agent_ideas"), fallback.agent_ideas),
                app_ideas=self._listify(data.get("app_ideas"), fallback.app_ideas),
                monetization_ideas=self._listify(data.get("monetization_ideas"), fallback.monetization_ideas),
                commercial_potential=str(data.get("commercial_potential", "medium")),
                confidence=float(data.get("confidence", 0.5)),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Product insight analysis failed, using fallback: %s", exc)
            return fallback


class RateLimitError(Exception):
    pass


class LLMCallError(Exception):
    pass
