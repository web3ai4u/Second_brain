"""Tests for the classify module."""

import unittest

from second_brain.classify import classify_document
from second_brain.config import CATEGORIES
from second_brain.models import (
    ClassificationDecision,
    Document,
    ExtractedContent,
)


def _make_doc(filename="test.txt"):
    return Document(
        id="test-doc-id",
        original_filename=filename,
        detected_format="text",
        file_size=100,
        sha256="fake",
        source_path="/fake/path",
    )


def _make_content(text):
    return ExtractedContent(
        id="test-content-id",
        document_id="test-doc-id",
        extracted_text=text,
        extraction_method="plain_text_read",
    )


class TestClassifyByExtension(unittest.TestCase):
    def test_md_classified_as_notes(self):
        doc = _make_doc("readme.md")
        content = _make_content("Some generic content")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "notes")

    def test_csv_classified_as_data(self):
        doc = _make_doc("report.csv")
        content = _make_content("col1,col2\n1,2")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "data")

    def test_log_classified_as_journal(self):
        doc = _make_doc("app.log")
        content = _make_content("2024-01-01 INFO: started")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "journal")


class TestClassifyByKeywords(unittest.TestCase):
    def test_journal_keywords(self):
        doc = _make_doc("entry.txt")
        content = _make_content("Journal entry for today. Diary note about the day.")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "journal")

    def test_code_keywords(self):
        doc = _make_doc("snippet.txt")
        content = _make_content("def main():\n    import os\n    class App: pass")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "code")

    def test_finance_keywords(self):
        doc = _make_doc("budget.txt")
        content = _make_content("Invoice #123. Payment due. Budget report for Q4.")
        decision, summary, events = classify_document(doc, content)
        self.assertEqual(decision.chosen_category, "finance")


class TestClassifyLowConfidence(unittest.TestCase):
    def test_no_signal_flags_review(self):
        doc = _make_doc("random.dat")
        content = _make_content("asdf qwer zxcv")
        decision, summary, events = classify_document(doc, content)
        self.assertTrue(decision.requires_manual_review)
        self.assertEqual(decision.chosen_category, "other")

    def test_extension_only_flags_review(self):
        doc = _make_doc("document.txt")
        content = _make_content("Generic text without keywords")
        decision, summary, events = classify_document(doc, content)
        self.assertTrue(decision.requires_manual_review)


class TestDecisionContract(unittest.TestCase):
    def test_contract_has_all_fields(self):
        doc = _make_doc("test.md")
        content = _make_content("Test content")
        decision, _, _ = classify_document(doc, content)
        self.assertTrue(decision.contract_version)
        self.assertGreater(len(decision.allowed_categories), 0)
        self.assertIn(decision.chosen_category, decision.allowed_categories)
        self.assertGreaterEqual(decision.confidence, 0.0)
        self.assertLessEqual(decision.confidence, 1.0)

    def test_chosen_category_is_valid(self):
        doc = _make_doc("anything.txt")
        content = _make_content("anything")
        decision, _, _ = classify_document(doc, content)
        self.assertIn(decision.chosen_category, CATEGORIES)


class TestSummaryGeneration(unittest.TestCase):
    def test_summary_from_content(self):
        doc = _make_doc("test.txt")
        content = _make_content("This is the first line.\nSecond line here.")
        _, summary, _ = classify_document(doc, content)
        self.assertTrue(summary)
        self.assertIn("first line", summary.lower())


if __name__ == "__main__":
    unittest.main()
