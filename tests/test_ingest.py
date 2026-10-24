"""Tests for the ingest module."""

import tempfile
import unittest
from pathlib import Path

from second_brain.config import Config
from second_brain.ingest import (
    DuplicateFileError,
    EmptyFileError,
    FileTooLargeError,
    IngestError,
    PathTraversalError,
    UnsupportedFormatError,
    ingest_file,
)
from second_brain.storage import Storage


class TestIngestValidFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_accept_txt_file(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("Hello, World!", encoding="utf-8")
        doc, events = ingest_file(test_file, self.config)
        self.assertEqual(doc.original_filename, "test.txt")
        self.assertEqual(doc.detected_format, "text")
        self.assertEqual(doc.file_size, 13)
        self.assertEqual(len(doc.sha256), 64)
        for evt in events:
            self.assertEqual(evt.document_id, doc.id)

    def test_accept_md_file(self):
        test_file = Path(self.tmpdir) / "notes.md"
        test_file.write_text("# My Notes\n\nSome content.", encoding="utf-8")
        doc, events = ingest_file(test_file, self.config)
        self.assertEqual(doc.original_filename, "notes.md")
        self.assertEqual(doc.detected_format, "text")


class TestIngestEmptyFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_empty_file_rejected(self):
        test_file = Path(self.tmpdir) / "empty.txt"
        test_file.write_text("", encoding="utf-8")
        with self.assertRaises(EmptyFileError):
            ingest_file(test_file, self.config)


class TestIngestUnsupportedFormat(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_unsupported_format_rejected(self):
        test_file = Path(self.tmpdir) / "image.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with self.assertRaises(UnsupportedFormatError) as ctx:
            ingest_file(test_file, self.config)
        self.assertIn(".png", str(ctx.exception))

    def test_exe_rejected(self):
        test_file = Path(self.tmpdir) / "program.exe"
        test_file.write_bytes(b"\x00" * 100)
        with self.assertRaises(UnsupportedFormatError):
            ingest_file(test_file, self.config)


class TestIngestDuplicate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_duplicate_detected(self):
        test_file = Path(self.tmpdir) / "original.txt"
        test_file.write_text("Same content here", encoding="utf-8")
        doc1, _ = ingest_file(test_file, self.config)
        self.storage.save_document(doc1)
        with self.assertRaises(DuplicateFileError) as ctx:
            ingest_file(test_file, self.config)
        self.assertIn(doc1.id, str(ctx.exception))


class TestIngestCorruptFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_nonexistent_file_raises(self):
        test_file = Path(self.tmpdir) / "nonexistent.txt"
        with self.assertRaises(IngestError):
            ingest_file(test_file, self.config)


class TestIngestPathTraversal(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_directory_rejected(self):
        dir_path = Path(self.tmpdir) / "subdir"
        dir_path.mkdir()
        with self.assertRaises(IngestError):
            ingest_file(dir_path, self.config)


class TestIngestEvents(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()
        self.storage = Storage(self.config)
        self.storage.initialize()

    def test_successful_ingest_creates_events(self):
        test_file = Path(self.tmpdir) / "event_test.txt"
        test_file.write_text("Content for event test", encoding="utf-8")
        doc, events = ingest_file(test_file, self.config)
        self.assertGreater(len(events), 0)
        for evt in events:
            self.assertTrue(evt.component)
            self.assertTrue(evt.operation)
            self.assertTrue(evt.status)


if __name__ == "__main__":
    unittest.main()
