"""Tests for storage module."""

import os
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from second_brain.config import Config
from second_brain.models import Document, ExtractedContent, ProcessingEvent
from second_brain.storage import Storage, StorageError


def _make_config(tmp):
    return Config(base_dir=Path(tmp))


def _make_doc():
    return Document(
        id="doc-001",
        original_filename="test.txt",
        detected_format="txt",
        file_size=100,
        sha256="a" * 64,
        source_path="/tmp/test.txt",
        created_at="2024-01-01T00:00:00Z",
        processing_status="pending",
        extraction_status="pending",
    )


def test_initialize():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        assert cfg.db_path.exists()


def test_save_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc = _make_doc()
        s.save_document(doc)
        got = s.get_document("doc-001")
        assert got is not None
        assert got.original_filename == "test.txt"
        assert got.sha256 == "a" * 64


def test_duplicate_sha256_raises():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc1 = _make_doc()
        s.save_document(doc1)
        doc2 = Document(
            id="doc-002",
            original_filename="other.txt",
            detected_format="txt",
            file_size=200,
            sha256="a" * 64,
            source_path="/tmp/other.txt",
            created_at="2024-01-02T00:00:00Z",
            processing_status="pending",
            extraction_status="pending",
        )
        try:
            s.save_document(doc2)
            assert False, "Should have raised"
        except StorageError:
            pass


def test_find_by_sha256():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc = _make_doc()
        s.save_document(doc)
        found = s.find_by_sha256("a" * 64)
        assert found is not None
        assert found.id == "doc-001"


def test_list_documents():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc = _make_doc()
        s.save_document(doc)
        docs = s.list_documents()
        assert len(docs) == 1


def test_save_event():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        evt = ProcessingEvent(
            id="evt-001",
            document_id="doc-001",
            timestamp="2024-01-01T00:00:00Z",
            component="ingest",
            operation="validate",
            status="success",
        )
        s.save_event(evt)
        events = s.get_events("doc-001")
        assert len(events) == 1
        assert events[0].component == "ingest"


def test_save_extracted_content():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc = _make_doc()
        s.save_document(doc)
        content = ExtractedContent(
            id="ext-001",
            document_id="doc-001",
            extracted_text="Hello world",
            extraction_method="utf8",
            extraction_version="1.0",
            created_at="2024-01-01T00:00:00Z",
        )
        s.save_extracted_content(content)
        got = s.get_extracted_content("doc-001")
        assert got is not None
        assert got.extracted_text == "Hello world"


def test_backup():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _make_config(tmp)
        s = Storage(cfg)
        s.initialize()
        doc = _make_doc()
        s.save_document(doc)
        bp = s.backup(cfg)
        assert bp.exists()
