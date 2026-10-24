"""Classification module - Layer B (semantic decisions)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .config import CATEGORIES, CATEGORY_KEYWORDS, SupportedFormats
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


def _classify_by_extension(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    ext_map = {
        ".md": "notes",
        ".markdown": "notes",
        ".rst": "reference",
        ".log": "journal",
        ".csv": "data",
        ".txt": "notes",
    }
    return ext_map.get(suffix)


def _classify_by_keywords(text: str) -> tuple[str | None, int, list[str]]:
    text_lower = text[:_KEYWORD_SCAN_LIMIT].lower()
    best_category: str | None = None
    best_hits = 0
    matched_keywords: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = []
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


def classify_document(
    document: Document,
    extracted: ExtractedContent,
) -> tuple[ClassificationDecision, str, list[ProcessingEvent]]:
    events: list[ProcessingEvent] = []
    text = extracted.extracted_text
    ext_category = _classify_by_extension(document.original_filename)
    criteria: list[str] = []
    if ext_category:
        criteria.append(f"extension_hint:{ext_category}")
    kw_category, kw_hits, matched_kw = _classify_by_keywords(text)
    if kw_category:
        criteria.append(f"keyword_hint:{kw_category}(hits={kw_hits})")
    if kw_hits >= _STRONG_MATCH_THRESHOLD and kw_category:
        chosen = kw_category
        confidence = 0.8
    elif ext_category:
        chosen = ext_category
        confidence = 0.6
    elif kw_category:
        chosen = kw_category
        confidence = 0.5
    else:
        chosen = "other"
        confidence = 0.2
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
    )
    summary = _generate_summary(text)
    events.append(ProcessingEvent(
        document_id=document.id,
        component="classify", operation="classify",
        status="success",
        sanitized_message=(
            f"Category: {chosen} (confidence: {confidence:.2f}, "
            f"review: {requires_review})"
        ),
    ))
    return decision, summary, events
