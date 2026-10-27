from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


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


class ProductInsightAnalyzer:
    """Turns raw notes into product, course, and agent opportunities."""

    def __init__(self, llm_client: Optional[Any] = None):
        self.llm_client = llm_client

    def _safe_json(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start:end + 1])
            raise ValueError("LLM response was not valid JSON")

    def analyze(self, text: str) -> BusinessInsight:
        if not self.llm_client or not getattr(self.llm_client, "is_available", False):
            return BusinessInsight(
                topic="unknown",
                audience="general knowledge workers",
                value_proposition="The material may be useful for a course, agent, or small product but needs manual review.",
                course_ideas=["Turn this into a short digital course or workshop."],
                agent_ideas=["Build a document-intake agent to structure the content."],
                app_ideas=["Create a lightweight local knowledge app around these notes."],
                monetization_ideas=["Offer consulting, templates, or a paid mini-course."],
                commercial_potential="medium",
                confidence=0.35,
            )

        payload = self.llm_client.analyze_for_products(text)
        data = self._safe_json(payload.content)
        return BusinessInsight(
            topic=data.get("topic", "unknown"),
            audience=data.get("audience", "general audience"),
            value_proposition=data.get("value_proposition", "No value proposition extracted."),
            course_ideas=data.get("course_ideas", ["Short micro-course based on the material."]),
            agent_ideas=data.get("agent_ideas", ["Prototype a personal knowledge agent."]),
            app_ideas=data.get("app_ideas", ["Turn notes into a small local app."]),
            monetization_ideas=data.get("monetization_ideas", ["Sell templates or a course."]),
            commercial_potential=data.get("commercial_potential", "medium"),
            confidence=float(data.get("confidence", 0.5)),
        )
