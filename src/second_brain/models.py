from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Document:
    id: str = field(default_factory=_new_id)
    original_filename: str = ""
    detected_format: str = ""
    file_size: int = 0
    sha256: str = ""
    source_path: str = ""
    created_at: str = field(default_factory=_utc_now)
    processed_at: Optional[str] = None
    processing_status: str = "pending"
    extraction_status: str = "pending"
    category: Optional[str] = None
    summary: Optional[str] = None
    action_hint: Optional[str] = None
    metadata_json: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ExtractedContent:
    id: str = field(default_factory=_new_id)
    document_id: str = ""
    extracted_text: str = ""
    extraction_method: str = ""
    extraction_version: str = "0.1.0"
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ProcessingEvent:
    id: str = field(default_factory=_new_id)
    document_id: str = ""
    timestamp: str = field(default_factory=_utc_now)
    component: str = ""
    operation: str = ""
    status: str = ""
    error_type: Optional[str] = None
    sanitized_message: Optional[str] = None
    run_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClassificationDecision:
    document_id: str = ""
    contract_version: str = "1.0"
    allowed_categories: list = field(default_factory=list)
    chosen_category: str = ""
    confidence: float = 0.0
    criteria_used: list = field(default_factory=list)
    requires_manual_review: bool = True
    manual_review_reason: Optional[str] = None
    action_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
