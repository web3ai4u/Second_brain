"""Secure ingestion logic for Second Brain MVP."""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from .config import Config
from .models import Document, ProcessingEvent

logger = logging.getLogger(__name__)

_DANGEROUS_NAMES = frozenset({"", ".", ".."})


class IngestError(Exception):
    pass


class UnsupportedFormatError(IngestError):
    pass


class FileTooLargeError(IngestError):
    pass


class PathTraversalError(IngestError):
    pass


class DuplicateFileError(IngestError):
    pass


class EmptyFileError(IngestError):
    pass


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_format(file_path: Path, config: Config) -> str:
    suffix = file_path.suffix.lower()
    if suffix in config.formats.all_extensions:
        return "text"
    raise UnsupportedFormatError(
        f"Format '{suffix}' is not supported. "
        f"Supported: {sorted(config.formats.all_extensions)}"
    )


def _validate_path(file_path: Path, allowed_dir: Path) -> Path:
    try:
        resolved = file_path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise IngestError(f"Path does not exist: {file_path}") from exc

    if not resolved.is_file():
        raise IngestError(f"Path does not point to a regular file: {resolved}")

    allowed_root = allowed_dir.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise PathTraversalError(
            f"Path escapes the allowed workspace: {resolved}"
        ) from exc

    return resolved


def _check_size(file_path: Path, max_bytes: int) -> int:
    size = file_path.stat().st_size
    if size == 0:
        raise EmptyFileError("File is empty (0 bytes).")
    if size > max_bytes:
        raise FileTooLargeError(
            f"File size {size} bytes exceeds limit {max_bytes} bytes."
        )
    return size


def ingest_file(
    source_path: str | Path,
    config: Config,
    allow_duplicate: bool = False,
) -> tuple[Document, list[ProcessingEvent]]:
    events: list[ProcessingEvent] = []
    source = Path(source_path)

    safe_root = config.base_dir.resolve().parent
    try:
        resolved = _validate_path(source, safe_root)
    except IngestError as e:
        evt = ProcessingEvent(
            component="ingest",
            operation="validate_path",
            status="failure",
            error_type=type(e).__name__,
            sanitized_message=str(e),
        )
        events.append(evt)
        raise

    filename = resolved.name
    if filename in _DANGEROUS_NAMES:
        raise IngestError(f"Dangerous filename rejected: '{filename}'")
    if len(filename) > config.limits.max_filename_length:
        raise IngestError(
            f"Filename exceeds allowed length: {len(filename)} > "
            f"{config.limits.max_filename_length}"
        )

    try:
        detected_format = _detect_format(resolved, config)
        events.append(
            ProcessingEvent(
                component="ingest",
                operation="detect_format",
                status="success",
                sanitized_message=f"Detected format: {detected_format}",
            )
        )
    except UnsupportedFormatError as e:
        events.append(
            ProcessingEvent(
                component="ingest",
                operation="detect_format",
                status="failure",
                error_type="UnsupportedFormatError",
                sanitized_message=str(e),
            )
        )
        raise

    try:
        file_size = _check_size(resolved, config.limits.max_file_size_bytes)
        events.append(
            ProcessingEvent(
                component="ingest",
                operation="check_size",
                status="success",
                sanitized_message=f"File size: {file_size} bytes",
            )
        )
    except (FileTooLargeError, EmptyFileError) as e:
        events.append(
            ProcessingEvent(
                component="ingest",
                operation="check_size",
                status="failure",
                error_type=type(e).__name__,
                sanitized_message=str(e),
            )
        )
        raise

    sha256 = _compute_sha256(resolved)
    events.append(
        ProcessingEvent(
            component="ingest",
            operation="compute_hash",
            status="success",
            sanitized_message=f"SHA-256: {sha256[:16]}...",
        )
    )

    from .storage import Storage

    storage = Storage(config)
    existing = storage.find_by_sha256(sha256)
    if existing and not allow_duplicate:
        events.append(
            ProcessingEvent(
                component="ingest",
                operation="duplicate_check",
                status="failure",
                error_type="DuplicateFileError",
                sanitized_message=f"Duplicate of document {existing.id}",
            )
        )
        raise DuplicateFileError(
            f"File already ingested as document {existing.id} "
            f"(filename: {existing.original_filename})"
        )
    events.append(
        ProcessingEvent(
            component="ingest",
            operation="duplicate_check",
            status="success",
            sanitized_message="No duplicate found",
        )
    )

    config.ensure_dirs()
    dest_dir = config.originals_dir
    dest_path = dest_dir / f"{sha256}_{filename}"
    if not dest_path.exists():
        shutil.copy2(resolved, dest_path)
    events.append(
        ProcessingEvent(
            component="ingest",
            operation="copy_original",
            status="success",
            sanitized_message=f"Copied to {dest_path.name}",
        )
    )

    doc = Document(
        original_filename=filename,
        detected_format=detected_format,
        file_size=file_size,
        sha256=sha256,
        source_path=str(dest_path),
        processing_status="pending",
        extraction_status="pending",
    )
    events.append(
        ProcessingEvent(
            document_id=doc.id,
            component="ingest",
            operation="create_record",
            status="success",
            sanitized_message=f"Document {doc.id} created",
        )
    )

    for evt in events:
        evt.document_id = doc.id

    return doc, events
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet


@dataclass(frozen=True)
class Limits:
    max_file_size_bytes: int = 50 * 1024 * 1024
    max_extracted_text_chars: int = 2 * 1024 * 1024
    max_filename_length: int = 255
    max_archive_entries: int = 10_000
    max_retry_attempts: int = 3
    network_timeout_seconds: float = 30.0


@dataclass(frozen=True)
class SupportedFormats:
    text_extensions: FrozenSet[str] = frozenset({
        ".txt",
        ".md",
        ".markdown",
        ".rst",
        ".log",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".html",
        ".htm",
        ".xml",
        ".py",
        ".js",
        ".ts",
    })

    @property
    def all_extensions(self) -> FrozenSet[str]:
        return self.text_extensions


@dataclass
class Config:
    base_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SECOND_BRAIN_DIR", str(Path.home() / ".second-brain"))
        )
    )
    limits: Limits = field(default_factory=Limits)
    formats: SupportedFormats = field(default_factory=SupportedFormats)

    @property
    def db_path(self) -> Path:
        return self.base_dir / "second_brain.db"

    @property
    def originals_dir(self) -> Path:
        return self.base_dir / "originals"

    @property
    def exports_dir(self) -> Path:
        return self.base_dir / "exports"

    @property
    def backup_dir(self) -> Path:
        return self.base_dir / "backups"

    @property
    def log_path(self) -> Path:
        return self.base_dir / "second_brain.log"

    @property
    def workspace_root(self) -> Path:
        return self.base_dir.resolve().parent

    def ensure_dirs(self) -> None:
        for d in (
            self.base_dir,
            self.originals_dir,
            self.exports_dir,
            self.backup_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


CATEGORIES: tuple[str, ...] = (
    "notes",
    "journal",
    "reference",
    "code",
    "config",
    "data",
    "correspondence",
    "finance",
    "legal",
    "research",
    "other",
)

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "journal": ["diary", "journal", "entry", "dnevnik", "zapis"],
    "reference": ["reference", "manual", "guide", "docs", "spravka", "rukovodstvo"],
    "code": ["def ", "class ", "import ", "function", "const ", "let ", "var "],
    "config": ["config", "settings", "preferences", "nastrojki"],
    "data": ["csv", "json", "yaml", "table", "dataset", "tablica", "dannye"],
    "correspondence": ["dear", "hello", "hi ", "regards", "privet", "zdravstvujte"],
    "finance": ["invoice", "receipt", "payment", "budget", "schet", "byudzhet"],
    "legal": ["contract", "agreement", "terms", "policy", "dogovor", "soglashenie"],
    "research": ["abstract", "hypothesis", "methodology", "study", "issledovanie"],
    "notes": ["todo", "note", "reminder", "zametka", "napominanie"],
}
# README content

# Project README rewritten to describe the actual MVP status and safe local-first operation.

"""
# Second Brain — Personal Knowledge System MVP

Local-first system for ingesting, classifying and storing digital materials with transparent provenance.

## What works now

This MVP focuses on one verified scenario: a user selects one local text file, the system validates it, extracts text, performs heuristic classification, saves the document record, and keeps the original file plus export metadata.

Implemented in the current branch:

- file validation and security checks
- SHA-256 hashing and duplicate detection
- plain-text extraction
- basic category classification and summary generation
- SQLite storage with document, extracted content and event logs
- export to JSON and backup/restore of the local database
- CLI entry point for ingest/list/show/export/backup/restore

## Important constraints

- This is a local-first MVP, not a multi-agent system.
- LLM integration remains optional and falls back to heuristics without requiring external services.
- OCR, PDF extraction, archive unpacking, and semantic search are intentionally deferred.

## Quick start

```bash
git clone https://github.com/web3ai4u/Second_brain.git
cd Second_brain
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
PYTHONPATH=src python -m second_brain ingest ./example.txt
PYTHONPATH=src python -m second_brain list
PYTHONPATH=src python -m second_brain show <doc_id>
```

## Architecture

Three layers remain intentionally simple:

1. Layer A: optional generation / LLM classification adapter
2. Layer B: decision layer with deterministic heuristic rules
3. Layer C: filesystem, hashing, SQLite, validation, export and backups

## Data model

The project stores:

- documents
- extracted_content
- processing_events

This preserves the distinction between original content, extracted text, model decisions and audit events.

## Security

- no secrets committed to the repository
- .env is excluded from Git
- all external API calls are opt-in
- paths are checked to prevent accidental traversal outside the trusted workspace
- backups are created locally and are not treated as verified until restored in a test flow

## Current status and limitations

This repository is an MVP prototype, not an all-in-one personal knowledge platform yet. The verified scenario is intentionally narrow and production-grade features remain explicit follow-up work.

## Testing

The repository includes pytest-based tests for ingest, extract, classification and storage.

To run them locally:

```bash
PYTHONPATH=src pytest tests -q
```

If a check cannot be executed in the current environment, it must be reported as NOT RUN rather than as PASS.

## License

This project does not currently declare a custom license in the repository. The existing files must be reviewed before redistribution beyond the current project scope.
"""

# This file intentionally replaced the previous README with an honest MVP description.

"""
# Second Brain — Personal Knowledge System MVP

Local-first system for ingesting, classifying and storing digital materials with transparent provenance.

## What works now

This MVP focuses on one verified scenario: a user selects one local text file, the system validates it, extracts text, performs heuristic classification, saves the document record, and keeps the original file plus export metadata.

Implemented in the current branch:

- file validation and security checks
- SHA-256 hashing and duplicate detection
- plain-text extraction
- basic category classification and summary generation
- SQLite storage with document, extracted content and event logs
- export to JSON and backup/restore of the local database
- CLI entry point for ingest/list/show/export/backup/restore

## Important constraints

- This is a local-first MVP, not a multi-agent system.
- LLM integration remains optional and falls back to heuristics without requiring external services.
- OCR, PDF extraction, archive unpacking, and semantic search are intentionally deferred.

## Quick start

```bash
git clone https://github.com/web3ai4u/Second_brain.git
cd Second_brain
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
PYTHONPATH=src python -m second_brain ingest ./example.txt
PYTHONPATH=src python -m second_brain list
PYTHONPATH=src python -m second_brain show <doc_id>
```

## Architecture

Three layers remain intentionally simple:

1. Layer A: optional generation / LLM classification adapter
2. Layer B: decision layer with deterministic heuristic rules
3. Layer C: filesystem, hashing, SQLite, validation, export and backups

## Data model

The project stores:

- documents
- extracted_content
- processing_events

This preserves the distinction between original content, extracted text, model decisions and audit events.

## Security

- no secrets committed to the repository
- .env is excluded from Git
- all external API calls are opt-in
- paths are checked to prevent accidental traversal outside the trusted workspace
- backups are created locally and are not treated as verified until restored in a test flow

## Current status and limitations

This repository is an MVP prototype, not an all-in-one personal knowledge platform yet. The verified scenario is intentionally narrow and production-grade features remain explicit follow-up work.

## Testing

The repository includes pytest-based tests for ingest, extract, classification and storage.

To run them locally:

```bash
PYTHONPATH=src pytest tests -q
```

If a check cannot be executed in the current environment, it must be reported as NOT RUN rather than as PASS.

## License

This project does not currently declare a custom license in the repository. The existing files must be reviewed before redistribution beyond the current project scope.
"""

# Actual README content follows below.
# Second Brain — Personal Knowledge System MVP

Local-first system for ingesting, classifying and storing digital materials with transparent provenance.

## What works now

This MVP focuses on one verified scenario: a user selects one local text file, the system validates it, extracts text, performs heuristic classification, saves the document record, and keeps the original file plus export metadata.

Implemented in the current branch:

- file validation and security checks
- SHA-256 hashing and duplicate detection
- plain-text extraction
- basic category classification and summary generation
- SQLite storage with document, extracted content and event logs
- export to JSON and backup/restore of the local database
- CLI entry point for ingest/list/show/export/backup/restore

## Important constraints

- This is a local-first MVP, not a multi-agent system.
- LLM integration remains optional and falls back to heuristics without requiring external services.
- OCR, PDF extraction, archive unpacking, and semantic search are intentionally deferred.

## Quick start

```bash
git clone https://github.com/web3ai4u/Second_brain.git
cd Second_brain
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
PYTHONPATH=src python -m second_brain ingest ./example.txt
PYTHONPATH=src python -m second_brain list
PYTHONPATH=src python -m second_brain show <doc_id>
```

## Architecture

Three layers remain intentionally simple:

1. Layer A: optional generation / LLM classification adapter
2. Layer B: decision layer with deterministic heuristic rules
3. Layer C: filesystem, hashing, SQLite, validation, export and backups

## Data model

The project stores:

- documents
- extracted_content
- processing_events

This preserves the distinction between original content, extracted text, model decisions and audit events.

## Security

- no secrets committed to the repository
- .env is excluded from Git
- all external API calls are opt-in
- paths are checked to prevent accidental traversal outside the trusted workspace
- backups are created locally and are not treated as verified until restored in a test flow

## Current status and limitations

This repository is an MVP prototype, not an all-in-one personal knowledge platform yet. The verified scenario is intentionally narrow and production-grade features remain explicit follow-up work.

## Testing

The repository includes pytest-based tests for ingest, extract, classification and storage.

To run them locally:

```bash
PYTHONPATH=src pytest tests -q
```

If a check cannot be executed in the current environment, it must be reported as NOT RUN rather than as PASS.

## License

This project does not currently declare a custom license in the repository. The existing files must be reviewed before redistribution beyond the current project scope.
