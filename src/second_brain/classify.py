from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from .config import ACTION_SUGGESTIONS, CATEGORIES, CATEGORY_KEYWORDS
from .llm_client import LLMClient
from .models import (
    ClassificationDecision,
    Document,
    ExtractedContent,
    ProcessingEvent,
)

logger = logging.getLogger(__name__)

_STRONG_MATCH_THRESHOLD = 2
_SUMMARY_MAX_CHARS = 200
_KEYWORD_SCAN_LIMIT = 5000


class ClassificationError(Exception):
    pass


def suggest_action(category: str) -> list[str]:
    category_name = category.lower()
    return ACTION_SUGGESTIONS.get(category_name, ACTION_SUGGESTIONS["other"]).copy()


def _classify_by_extension(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    ext_map = {
        ".md": "notes",
        ".markdown": "notes",
        ".rst": "reference",
        ".log": "journal",
        ".csv": "data",
        ".txt": "notes",
        ".json": "data",
        ".yaml": "config",
        ".yml": "config",
        ".py": "code",
        ".js": "code",
        ".ts": "code",
    }
    return ext_map.get(suffix)


def _classify_by_keywords(text: str) -> tuple[str | None, int, list[str]]:
    text_lower = text[:_KEYWORD_SCAN_LIMIT].lower()
    best_category: str | None = None
    best_hits = 0
    matched_keywords: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits: list[str] = []
        for kw in keywords:
            count = len(re.findall(re.escape(kw.lower()), text_lower))
            if count > 0:
                hits.extend([kw] * count)
        if len(hits) > best_hits:
            best_hits = len(hits)
            best_category = category
            matched_keywords = hits
    return best_category, best_hits, matched_keywords


def _generate_summary(text: str) -> str:
    lines = text.strip().splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:_SUMMARY_MAX_CHARS]
    if lines:
        return lines[0].strip()[:_SUMMARY_MAX_CHARS]
    return ""


def _heuristic_classify(document: Document, text: str) -> tuple[str, float, list[str]]:
    criteria: list[str] = []
    ext_category = _classify_by_extension(document.original_filename)
    if ext_category:
        criteria.append(f"extension_hint:{ext_category}")
    kw_category, kw_hits, matched_kw = _classify_by_keywords(text)
    if kw_category:
        criteria.append(f"keyword_hint:{kw_category}(hits={kw_hits})")
    if kw_hits >= _STRONG_MATCH_THRESHOLD and kw_category:
        return kw_category, 0.8, criteria
    if ext_category:
        return ext_category, 0.6, criteria
    if kw_category:
        return kw_category, 0.5, criteria
    return "other", 0.2, criteria


def classify_document(
    document: Document,
    extracted: ExtractedContent,
    llm_client: Optional[LLMClient] = None,
) -> tuple[ClassificationDecision, str, list[ProcessingEvent]]:
    events: list[ProcessingEvent] = []
    text = extracted.extracted_text
    method = "heuristic"

    chosen = None
    confidence = 0.0
    criteria: list[str] = []
    llm_model = None

    if llm_client and llm_client.is_available:
        try:
            llm_resp = llm_client.classify(text, list(CATEGORIES))
            if llm_resp:
                chosen = llm_resp.content
                confidence = 0.9
                method = "llm"
                llm_model = llm_resp.model
                criteria.append(f"llm:{llm_model}")
                events.append(
                    ProcessingEvent(
                        document_id=document.id,
                        component="classify",
                        operation="llm_classify",
                        status="success",
                        sanitized_message=f"LLM: {chosen} via {llm_model}",
                    )
                )
        except Exception as e:
            logger.warning("LLM classification failed: %s", e)
            events.append(
                ProcessingEvent(
                    document_id=document.id,
                    component="classify",
                    operation="llm_classify",
                    status="failed",
                    sanitized_message=f"LLM failed: {type(e).__name__}",
                )
            )

    if chosen is None:
        chosen, confidence, criteria = _heuristic_classify(document, text)

    action_hints = suggest_action(chosen)
    requires_review = confidence < 0.7
    review_reason = None
    if requires_review:
        if confidence < 0.3:
            review_reason = "No strong category signal detected"
        elif confidence < 0.7:
            review_reason = "Classification based on weak signal only"

    decision = ClassificationDecision(
        document_id=document.id,
        allowed_categories=list(CATEGORIES),
        chosen_category=chosen,
        confidence=confidence,
        criteria_used=criteria,
        requires_manual_review=requires_review,
        manual_review_reason=review_reason,
        action_hints=action_hints,
    )

    summary = _generate_summary(text)
    events.append(
        ProcessingEvent(
            document_id=document.id,
            component="classify",
            operation="classify",
            status="success",
            sanitized_message=(
                f"- {chosen} (confidence: {confidence:.2f}, method: {method}, review: {requires_review})"
            ),
        )
    )

    return decision, summary, events
