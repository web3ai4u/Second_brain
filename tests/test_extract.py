"""Tests for the extract module."""

import tempfile
import unittest
from pathlib import Path

from second_brain.config import Config, Limits
from second_brain.extract import extract_text, ExtractionError
from second_brain.models import Document


class TestExtractUTF8(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()

    def test_extract_utf8_text(self):
        test_file = Path(self.tmpdir) / "utf8.txt"
        content = "Hello, world!"
        test_file.write_text(content, encoding="utf-8")
        doc = Document(
            original_filename="utf8.txt",
            source_path=str(test_file),
            detected_format="text",
            file_size=test_file.stat().st_size,
            sha256="fake",
        )
        extracted, events = extract_text(doc, self.config)
        self.assertEqual(extracted.extracted_text, content)
        self.assertEqual(extracted.extraction_method, "plain_text_read")
        self.assertGreater(len(events), 0)


class TestExtractLatin1Fallback(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()

    def test_latin1_fallback(self):
        test_file = Path(self.tmpdir) / "latin1.txt"
        content_bytes = b"Hello \xe9 world"
        test_file.write_bytes(content_bytes)
        doc = Document(
            original_filename="latin1.txt",
            source_path=str(test_file),
            detected_format="text",
            file_size=len(content_bytes),
            sha256="fake",
        )
        extracted, events = extract_text(doc, self.config)
        self.assertIn("Hello", extracted.extracted_text)


class TestExtractMissingFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(base_dir=Path(self.tmpdir) / ".second-brain")
        self.config.ensure_dirs()

    def test_missing_file_raises(self):
        doc = Document(
            original_filename="missing.txt",
            source_path=str(Path(self.tmpdir) / "nonexistent.txt"),
            detected_format="text",
            file_size=100,
            sha256="fake",
        )
        with self.assertRaises(ExtractionError):
            extract_text(doc, self.config)


class TestExtractSizeLimit(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = Config(
            base_dir=Path(self.tmpdir) / ".second-brain",
            limits=Limits(max_extracted_text_chars=100),
        )
        self.config.ensure_dirs()

    def test_text_truncated_at_limit(self):
        test_file = Path(self.tmpdir) / "large.txt"
        content = "A" * 500
        test_file.write_text(content, encoding="utf-8")
        doc = Document(
            original_filename="large.txt",
            source_path=str(test_file),
            detected_format="text",
            file_size=len(content),
            sha256="fake",
        )
        extracted, events = extract_text(doc, self.config)
        self.assertLessEqual(len(extracted.extracted_text), 100)


if __name__ == "__main__":
    unittest.main()
