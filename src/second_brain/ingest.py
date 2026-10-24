"""File ingestion module - Layer C (deterministic)."""

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
    resolved = file_path.resolve()
    if not resolved.is_file():
        raise IngestError(f"Path does not point to a regular file: {resolved}")
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

    try:
        resolved = _validate_path(source, Path.cwd())
    except IngestError as e:
        evt = ProcessingEvent(
            component="ingest", operation="validate_path",
            status="failure", error_type=type(e).__name__,
            sanitized_message=str(e),
        )
        events.append(evt)
        raise

    filename = resolved.name
    if filename in _DANGEROUS_NAMES:
        raise IngestError(f"Dangerous filename rejected: '{filename}'")

    try:
        detected_format = _detect_format(resolved, config)
        events.append(ProcessingEvent(
            component="ingest", operation="detect_format",
            status="success",
            sanitized_message=f"Detected format: {detected_format}",
        ))
    except UnsupportedFormatError as e:
        events.append(ProcessingEvent(
            component="ingest", operation="detect_format",
            status="failure", error_type="UnsupportedFormatError",
            sanitized_message=str(e),
        ))
        raise

    try:
        file_size = _check_size(resolved, config.limits.max_file_size_bytes)
        events.append(ProcessingEvent(
            component="ingest", operation="check_size",
            status="success",
            sanitized_message=f"File size: {file_size} bytes",
        ))
    except (FileTooLargeError, EmptyFileError) as e:
        events.append(ProcessingEvent(
            component="ingest", operation="check_size",
            status="failure", error_type=type(e).__name__,
            sanitized_message=str(e),
        ))
        raise

    sha256 = _compute_sha256(resolved)
    events.append(ProcessingEvent(
        component="ingest", operation="compute_hash",
        status="success",
        sanitized_message=f"SHA-256: {sha256[:16]}...",
    ))

    from .storage import Storage
    storage = Storage(config)
    existing = storage.find_by_sha256(sha256)
    if existing and not allow_duplicate:
        events.append(ProcessingEvent(
            component="ingest", operation="duplicate_check",
            status="failure", error_type="DuplicateFileError",
            sanitized_message=f"Duplicate of document {existing.id}",
        ))
        raise DuplicateFileError(
            f"File already ingested as document {existing.id} "
            f"(filename: {existing.original_filename})"
        )
    events.append(ProcessingEvent(
        component="ingest", operation="duplicate_check",
        status="success",
        sanitized_message="No duplicate found",
    ))

    config.ensure_dirs()
    dest_dir = config.originals_dir
    dest_path = dest_dir / f"{sha256}_{filename}"
    if not dest_path.exists():
        shutil.copy2(resolved, dest_path)
    events.append(ProcessingEvent(
        component="ingest", operation="copy_original",
        status="success",
        sanitized_message=f"Copied to {dest_path.name}",
    ))

    doc = Document(
        original_filename=filename,
        detected_format=detected_format,
        file_size=file_size,
        sha256=sha256,
        source_path=str(dest_path),
        processing_status="pending",
        extraction_status="pending",
    )
    events.append(ProcessingEvent(
        document_id=doc.id,
        component="ingest", operation="create_record",
        status="success",
        sanitized_message=f"Document {doc.id} created",
    ))

    for evt in events:
        evt.document_id = doc.id

    return doc, events
