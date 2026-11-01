from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ----------------------------
# Configuration
# ----------------------------

WATCH_DIR = Path("incoming")
DB_PATH = Path("file_intake.db")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ----------------------------
# Data model
# ----------------------------

@dataclass
class FileRecord:
    id: Optional[int] = None
    filename: str = ""
    source_path: str = ""
    sha256: str = ""
    size_bytes: int = 0
    mime_type: str = ""
    extension: str = ""
    category: str = ""
    action: str = ""
    created_at: str = ""
    extracted_text: str = ""


# ----------------------------
# Helper functions
# ----------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_text_from_file(path: Path, max_chars: int = 20000) -> str:
    """
    Extract text from common text files.
    Falls back to empty string for binary files.
    """
    try:
        with path.open("r", encoding="utf-8", errors="strict") as f:
            return f.read(max_chars)
    except UnicodeDecodeError:
        try:
            with path.open("r", encoding="latin-1", errors="strict") as f:
                return f.read(max_chars)
        except Exception:
            return ""
    except Exception:
        return ""


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def normalize_extension(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def classify_file(filename: str, text: str = "") -> tuple[str, str]:
    """
    Returns (category, action_suggestion)

    Categories:
      - notes
      - data
      - finance
      - code
      - image
      - archive
      - journal
      - review
    """
    lower_name = filename.lower()
    lower_text = text.lower()

    if lower_name.endswith((".md", ".txt", ".rst")):
        category = "notes"
        action = "Review and summarize into a personal index"
    elif lower_name.endswith((".csv", ".json", ".xlsx", ".tsv")):
        category = "data"
        action = "Normalize and archive structured data"
    elif lower_name.endswith((".pdf", ".docx", ".pptx")):
        category = "review"
        action = "Extract text and decide if it needs a human review"
    elif lower_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        category = "image"
        action = "Store in a photo archive and tag context"
    elif lower_name.endswith((".zip", ".tar", ".gz", ".rar")):
        category = "archive"
        action = "Inspect archive contents safely before processing"
    elif lower_name.endswith((".log", ".txt")) and any(
        k in lower_text for k in ["error", "warning", "failed", "exception"]
    ):
        category = "journal"
        action = "Flag for troubleshooting and keep as operational journal"
    elif lower_name.endswith((".py", ".js", ".ts", ".java", ".go", ".rs", ".sql")):
        category = "code"
        action = "Keep as implementation artifact and note the purpose"
    else:
        keyword_map = {
            "invoice": ("finance", "Extract payment details and file under finance"),
            "receipt": ("finance", "Extract payment details and file under finance"),
            "bank": ("finance", "Review for financial record keeping"),
            "budget": ("finance", "Review for budget tracking"),
            "travel": ("notes", "Add to trip notes and capture decisions"),
            "meeting": ("notes", "Summarize the decision and action items"),
            "todo": ("notes", "Convert into next-step list"),
            "error": ("journal", "Keep as incident log and investigate root cause"),
            "migration": ("code", "Track technical changes and validation steps"),
        }
        for kw, (cat, act) in keyword_map.items():
            if kw in lower_text or kw in lower_name:
                return cat, act

        category = "review"
        action = "Needs human classification review"

    return category, action


# ----------------------------
# SQLite storage
# ----------------------------


def init_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            source_path TEXT NOT NULL UNIQUE,
            sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mime_type TEXT NOT NULL,
            extension TEXT NOT NULL,
            category TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL,
            extracted_text TEXT
        )
        """
    )
    conn.commit()
    return conn


def insert_record(conn: sqlite3.Connection, rec: FileRecord) -> None:
    conn.execute(
        """
        INSERT INTO files (
            filename,
            source_path,
            sha256,
            size_bytes,
            mime_type,
            extension,
            category,
            action,
            created_at,
            extracted_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rec.filename,
            rec.source_path,
            rec.sha256,
            rec.size_bytes,
            rec.mime_type,
            rec.extension,
            rec.category,
            rec.action,
            rec.created_at,
            rec.extracted_text,
        ),
    )
    conn.commit()


def find_by_sha256(conn: sqlite3.Connection, sha256: str) -> Optional[FileRecord]:
    row = conn.execute(
        "SELECT * FROM files WHERE sha256 = ? LIMIT 1",
        (sha256,),
    ).fetchone()
    if row is None:
        return None

    return FileRecord(
        id=row[0],
        filename=row[1],
        source_path=row[2],
        sha256=row[3],
        size_bytes=row[4],
        mime_type=row[5],
        extension=row[6],
        category=row[7],
        action=row[8],
        created_at=row[9],
        extracted_text=row[10] or "",
    )


# ----------------------------
# Intake logic
# ----------------------------


def ingest_file(path: Path, conn: sqlite3.Connection) -> FileRecord:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.is_dir():
        raise ValueError(f"Not a file: {path}")

    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"Empty file: {path}")

    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {path} ({size} bytes)")

    source_path = str(path.resolve())

    sha = sha256_of_file(path)
    existing = find_by_sha256(conn, sha)
    if existing:
        raise ValueError(f"Duplicate file detected: {existing.source_path}")

    text = safe_text_from_file(path)
    category, action = classify_file(path.name, text)

    rec = FileRecord(
        filename=path.name,
        source_path=source_path,
        sha256=sha,
        size_bytes=size,
        mime_type=guess_mime(path),
        extension=normalize_extension(path),
        category=category,
        action=action,
        created_at=utc_now_iso(),
        extracted_text=text[:20000],
    )

    insert_record(conn, rec)
    return rec


def list_records(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, filename, source_path, sha256, size_bytes, mime_type,
               extension, category, action, created_at
        FROM files
        ORDER BY created_at DESC
        """
    ).fetchall()

    return [
        {
            "id": r[0],
            "filename": r[1],
            "source_path": r[2],
            "sha256": r[3],
            "size_bytes": r[4],
            "mime_type": r[5],
            "extension": r[6],
            "category": r[7],
            "action": r[8],
            "created_at": r[9],
        }
        for r in rows
    ]


# ----------------------------
# CLI
# ----------------------------


def ensure_watch_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_watch_dir(WATCH_DIR)
    conn = init_db(DB_PATH)

    print(f"Watching: {WATCH_DIR}")
    print(f"Database: {DB_PATH}")

    for entry in sorted(WATCH_DIR.iterdir()):
        if entry.is_file():
            try:
                rec = ingest_file(entry, conn)
                print(f"INGESTED: {rec.filename} -> {rec.category} / {rec.action}")
            except ValueError as e:
                print(f"SKIPPED: {entry.name} -> {e}")
            except Exception as e:
                print(f"ERROR: {entry.name} -> {e}")

    print("\nStored records:")
    for item in list_records(conn):
        print(json.dumps(item, indent=2))


if __name__ == "__main__":
    main()
