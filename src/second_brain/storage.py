"""SQLite storage module — Layer C (deterministic).

Handles:
- database initialization and schema migration
- CRUD for Document, ExtractedContent, ProcessingEvent
- duplicate detection by SHA-256
- export to JSON
- backup and restore
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Config
from .models import Document, ExtractedContent, ProcessingEvent

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    detected_format TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    source_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    category TEXT,
    summary TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS extracted_content (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    extracted_text TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_events (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    timestamp TEXT NOT NULL,
    component TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    error_type TEXT,
    sanitized_message TEXT,
    run_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_events_document_id ON processing_events(document_id);
CREATE INDEX IF NOT EXISTS idx_content_document_id ON extracted_content(document_id);
"""


class StorageError(Exception):
    """Base error for storage operations."""


class Storage:
    """SQLite-backed persistence layer."""

    def __init__(self, config: Config):
        self._config = config
        self._db_path = config.db_path

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with row factory."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        """Create database and tables if they don't exist."""
        self._config.ensure_dirs()
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def save_document(self, doc: Document) -> None:
        """Insert a new document record.

        Raises StorageError if a document with the same SHA-256
        already exists (duplicate detection at DB level).
        """
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO documents
                   (id, original_filename, detected_format, file_size,
                    sha256, source_path, created_at, processed_at,
                    processing_status, extraction_status, category,
                    summary, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc.id, doc.original_filename, doc.detected_format,
                 doc.file_size, doc.sha256, doc.source_path,
                 doc.created_at, doc.processed_at,
                 doc.processing_status, doc.extraction_status,
                 doc.category, doc.summary, doc.metadata_json),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise StorageError(f"Database integrity error: {e}") from e
        finally:
            conn.close()

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            if row is None:
                return None
            return Document(**dict(row))
        finally:
            conn.close()

    def find_by_sha256(self, sha256: str) -> Optional[Document]:
        """Find a document by its SHA-256 hash."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE sha256 = ?", (sha256,)
            ).fetchone()
            if row is None:
                return None
            return Document(**dict(row))
        finally:
            conn.close()

    def list_documents(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Document]:
        """List documents with optional filters."""
        conn = self._connect()
        try:
            query = "SELECT * FROM documents WHERE 1=1"
            params: list = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if status:
                query += " AND processing_status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [Document(**dict(r)) for r in rows]
        finally:
            conn.close()

    def update_document(self, doc: Document) -> None:
        """Update an existing document record."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO documents
                   (id, original_filename, detected_format, file_size,
                    sha256, source_path, created_at, processed_at,
                    processing_status, extraction_status, category,
                    summary, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc.id, doc.original_filename, doc.detected_format,
                 doc.file_size, doc.sha256, doc.source_path,
                 doc.created_at, doc.processed_at,
                 doc.processing_status, doc.extraction_status,
                 doc.category, doc.summary, doc.metadata_json),
            )
            conn.commit()
        finally:
            conn.close()

    def save_extracted_content(self, content: ExtractedContent) -> None:
        """Insert or replace extracted content."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO extracted_content
                   (id, document_id, extracted_text,
                    extraction_method, extraction_version, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (content.id, content.document_id, content.extracted_text,
                 content.extraction_method, content.extraction_version,
                 content.created_at),
            )
            conn.commit()
        finally:
            conn.close()

    def get_extracted_content(self, doc_id: str) -> Optional[ExtractedContent]:
        """Get extracted content for a document."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM extracted_content WHERE document_id = ?",
                (doc_id,),
            ).fetchone()
            if row is None:
                return None
            return ExtractedContent(**dict(row))
        finally:
            conn.close()

    def save_event(self, event: ProcessingEvent) -> None:
        """Insert a processing event."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO processing_events
                   (id, document_id, timestamp, component, operation,
                    status, error_type, sanitized_message, run_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event.id, event.document_id, event.timestamp,
                 event.component, event.operation, event.status,
                 event.error_type, event.sanitized_message, event.run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def save_events(self, events: list[ProcessingEvent]) -> None:
        """Save multiple processing events."""
        for evt in events:
            self.save_event(evt)

    def get_events(self, doc_id: str) -> list[ProcessingEvent]:
        """Get all processing events for a document."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM processing_events WHERE document_id = ? "
                "ORDER BY timestamp",
                (doc_id,),
            ).fetchall()
            return [ProcessingEvent(**dict(r)) for r in rows]
        finally:
            conn.close()

    def export_document_json(self, doc_id: str) -> Optional[str]:
        """Export a document and its extracted content as JSON."""
        doc = self.get_document(doc_id)
        if doc is None:
            return None
        content = self.get_extracted_content(doc_id)
        events = self.get_events(doc_id)
        export = {
            "document": doc.to_dict(),
            "extracted_content": content.to_dict() if content else None,
            "processing_events": [e.to_dict() for e in events],
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(export, ensure_ascii=False, indent=2)

    def export_all_json(self) -> str:
        """Export all documents as a single JSON array."""
        docs = self.list_documents(limit=10000)
        export_data = []
        for doc in docs:
            content = self.get_extracted_content(doc.id)
            export_data.append({
                "document": doc.to_dict(),
                "extracted_content": content.to_dict() if content else None,
            })
        return json.dumps(export_data, ensure_ascii=False, indent=2)

    def backup(self, config: Config) -> Path:
        """Create a timestamped backup of the database."""
        config.ensure_dirs()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = config.backup_dir / f"second_brain_{ts}.db"
        if config.db_path.exists():
            shutil.copy2(config.db_path, backup_path)
        return backup_path

    @staticmethod
    def restore(backup_path: Path, config: Config) -> None:
        """Restore the database from a backup file."""
        if not backup_path.exists():
            raise StorageError(f"Backup file not found: {backup_path}")
        if not backup_path.is_file():
            raise StorageError(f"Backup path is not a file: {backup_path}")
        shutil.copy2(backup_path, config.db_path)
