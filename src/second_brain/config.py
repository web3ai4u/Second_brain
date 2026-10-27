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
        ".pdf",
        ".doc",
        ".docx",
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
    def inbox_dir(self) -> Path:
        return self.base_dir / "inbox"

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
            self.inbox_dir,
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
    "journal": ["diary", "journal", "entry", "dnevnik", "zapis", "today", "log"],
    "reference": [
        "reference",
        "manual",
        "guide",
        "docs",
        "documentation",
        "spravka",
        "rukovodstvo",
    ],
    "code": [
        "def ",
        "class ",
        "import ",
        "function",
        "const ",
        "let ",
        "var ",
        "return ",
        "if ",
        "python",
        "javascript",
    ],
    "config": ["config", "settings", "preferences", "nastrojki", "yaml", "toml", "env"],
    "data": ["csv", "json", "yaml", "table", "dataset", "tablica", "dannye", "rows", "columns"],
    "correspondence": ["dear", "hello", "hi ", "regards", "privet", "zdravstvujte", "meeting"],
    "finance": ["invoice", "receipt", "payment", "budget", "expense", "schet", "byudzhet", "tax"],
    "legal": ["contract", "agreement", "terms", "policy", "dogovor", "soglashenie", "clause"],
    "research": ["abstract", "hypothesis", "methodology", "study", "issledovanie", "analysis", "experiment"],
    "notes": ["todo", "note", "reminder", "zametka", "napominanie", "idea", "summary"],
}

ACTION_SUGGESTIONS: dict[str, list[str]] = {
    "notes": ["Capture in the notes vault and summarize the next action.", "Create a follow-up task if this needs a decision."],
    "journal": ["Archive as a daily record and link it to the date context.", "Keep for personal timeline/history."],
    "reference": ["Save as reusable reference material.", "Tag as a source you may revisit."],
    "code": ["Treat as implementation material; review and keep with related project context.", "Add to the engineering backlog if it needs follow-up."],
    "config": ["Store with environment and setup docs.", "Verify whether it belongs to the active project config set."],
    "data": ["Keep in the data archive and note any schema assumptions.", "Validate source provenance and downstream uses."],
    "correspondence": ["Classify as communication history and answer if needed.", "Flag for action if a reply is required."],
    "finance": ["Move to financial records and check due dates/payments.", "Add a task for reconciliation or approval."],
    "legal": ["Store in legal / compliance archive and assess escalation needs.", "Review policy or contract obligations before acting."],
    "research": ["Keep as research artifact and note hypotheses/questions.", "Link to references or any next experiment."],
    "other": ["Review manually and decide whether this should become a structured category later.", "Placeholder: keep but mark for reclassification if needed."],
}
