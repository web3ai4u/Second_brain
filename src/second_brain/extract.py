"""Text extraction module - Layer C (deterministic)."""

from __future__ import annotations

import logging
from pathlib import Path

from .config import Config
from .models import Document, ExtractedContent, ProcessingEvent

logger = logging.getLogger(__name__)

EXTRACTION_METHOD = "plain_text_read"
EXTRACTION_VERSION = "0.1.0"


class ExtractionError(Exception):
    pass


class ExtractionSizeError(ExtractionError):
    pass


def extract_text(
    document: Document,
    config: Config,
) -> tuple[ExtractedContent, list[ProcessingEvent]]:
    events: list[ProcessingEvent] = []
    source = Path(document.source_path)

    if not source.exists():
        evt = ProcessingEvent(
            document_id=document.id,
            component="extract", operation="read_file",
            status="failure", error_type="FileNotFoundError",
            sanitized_message=f"Original file not found: {source.name}",
        )
        events.append(evt)
        raise ExtractionError(f"Original file not found: {source}")

    try:
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = source.read_text(encoding="latin-1")
            logger.warning(
                "File %s decoded as latin-1 (utf-8 failed)", source.name
            )
    except OSError as e:
        evt = ProcessingEvent(
            document_id=document.id,
            component="extract", operation="read_file",
            status="failure", error_type="OSError",
            sanitized_message=f"Could not read file: {source.name}",
        )
        events.append(evt)
        raise ExtractionError(f"Could not read file: {e}") from e

    events.append(ProcessingEvent(
        document_id=document.id,
        component="extract", operation="read_file",
        status="success",
        sanitized_message=f"Read {len(text)} chars from {source.name}",
    ))

    if len(text) > config.limits.max_extracted_text_chars:
        truncated = text[:config.limits.max_extracted_text_chars]
        events.append(ProcessingEvent(
            document_id=document.id,
            component="extract", operation="size_check",
            status="failure", error_type="ExtractionSizeError",
            sanitized_message=(
                f"Extracted text {len(text)} chars exceeds limit "
                f"{config.limits.max_extracted_text_chars}; truncated"
            ),
        ))
        text = truncated

    content = ExtractedContent(
        document_id=document.id,
        extracted_text=text,
        extraction_method=EXTRACTION_METHOD,
        extraction_version=EXTRACTION_VERSION,
    )
    events.append(ProcessingEvent(
        document_id=document.id,
        component="extract", operation="create_record",
        status="success",
        sanitized_message=f"ExtractedContent {content.id} created",
    ))

    return content, events
