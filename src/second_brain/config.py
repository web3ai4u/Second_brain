"""Configuration for Second Brain MVP."""

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
        ".txt", ".md", ".markdown", ".rst", ".log", ".csv",
    })

    @property
    def all_extensions(self) -> FrozenSet[str]:
        return self.text_extensions


@dataclass
class Config:
    base_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("SECOND_BRAIN_DIR", str(Path.home() / ".second-brain"))
    ))
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

    def ensure_dirs(self) -> None:
        for d in (self.base_dir, self.originals_dir,
                  self.exports_dir, self.backup_dir):
            d.mkdir(parents=True, exist_ok=True)


CATEGORIES: tuple[str, ...] = (
    "notes", "journal", "reference", "code", "config",
    "data", "correspondence", "finance", "legal", "research", "other",
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
