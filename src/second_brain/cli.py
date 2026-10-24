"""Command-line interface for Second Brain MVP."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Config
from .ingest import (
    DuplicateFileError,
    EmptyFileError,
    FileTooLargeError,
    IngestError,
    PathTraversalError,
    UnsupportedFormatError,
    ingest_file,
)
from .extract import extract_text, ExtractionError
from .classify import classify_document
from .storage import Storage, StorageError


def _setup_logging(config: Config) -> None:
    config.ensure_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(config.log_path), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def _cmd_ingest(args, config):
    storage = Storage(config)
    storage.initialize()
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1
    try:
        doc, ingest_events = ingest_file(file_path, config)
    except DuplicateFileError as e:
        print(f"Duplicate detected: {e}", file=sys.stderr)
        return 2
    except UnsupportedFormatError as e:
        print(f"Unsupported format: {e}", file=sys.stderr)
        return 3
    except FileTooLargeError as e:
        print(f"File too large: {e}", file=sys.stderr)
        return 4
    except EmptyFileError as e:
        print(f"Empty file: {e}", file=sys.stderr)
        return 5
    except IngestError as e:
        print(f"Ingest error: {e}", file=sys.stderr)
        return 1
    doc.processing_status = "processing"
    storage.save_document(doc)
    storage.save_events(ingest_events)
    try:
        content, extract_events = extract_text(doc, config)
    except ExtractionError as e:
        doc.processing_status = "failed"
        doc.extraction_status = "failed"
        storage.update_document(doc)
        print(f"Extraction error: {e}", file=sys.stderr)
        return 1
    doc.extraction_status = "completed"
    storage.save_extracted_content(content)
    storage.save_events(extract_events)
    decision, summary, classify_events = classify_document(doc, content)
    doc.category = decision.chosen_category
    doc.summary = summary
    doc.processing_status = "completed"
    from datetime import datetime, timezone
    doc.processed_at = datetime.now(timezone.utc).isoformat()
    storage.update_document(doc)
    storage.save_events(classify_events)
    print("Document ingested successfully!")
    print(f"  ID:       {doc.id}")
    print(f"  File:     {doc.original_filename}")
    print(f"  Size:     {doc.file_size} bytes")
    print(f"  SHA-256:  {doc.sha256[:16]}...")
    print(f"  Format:   {doc.detected_format}")
    print(f"  Category: {doc.category} (confidence: {decision.confidence:.2f})")
    return 0


def _cmd_list(args, config):
    storage = Storage(config)
    storage.initialize()
    docs = storage.list_documents(
        category=args.category, status=args.status, limit=args.limit,
    )
    if not docs:
        print("No documents found.")
        return 0
    print(f"{'ID':<36} {'Category':<12} {'Status':<12} {'Filename'}")
    print("-" * 90)
    for doc in docs:
        print(
            f"{doc.id:<36} {(doc.category or '?'):<12} "
            f"{doc.processing_status:<12} {doc.original_filename}"
        )
    return 0


def _cmd_show(args, config):
    storage = Storage(config)
    storage.initialize()
    doc = storage.get_document(args.doc_id)
    if doc is None:
        print(f"Document not found: {args.doc_id}", file=sys.stderr)
        return 1
    print(doc.to_json())
    content = storage.get_extracted_content(doc.id)
    if content:
        print("\n--- Extracted Content (first 500 chars) ---")
        print(content.extracted_text[:500])
    return 0


def _cmd_export(args, config):
    storage = Storage(config)
    storage.initialize()
    result = storage.export_document_json(args.doc_id)
    if result is None:
        print(f"Document not found: {args.doc_id}", file=sys.stderr)
        return 1
    config.ensure_dirs()
    export_path = config.exports_dir / f"{args.doc_id}.json"
    export_path.write_text(result, encoding="utf-8")
    print(f"Exported to: {export_path}")
    return 0


def _cmd_export_all(args, config):
    storage = Storage(config)
    storage.initialize()
    result = storage.export_all_json()
    config.ensure_dirs()
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    export_path = config.exports_dir / f"all_documents_{ts}.json"
    export_path.write_text(result, encoding="utf-8")
    print(f"Exported {len(json.loads(result))} documents to: {export_path}")
    return 0


def _cmd_backup(args, config):
    storage = Storage(config)
    storage.initialize()
    backup_path = storage.backup(config)
    print(f"Backup created: {backup_path}")
    return 0


def _cmd_restore(args, config):
    backup_path = Path(args.backup_path)
    try:
        Storage.restore(backup_path, config)
        print(f"Database restored from: {backup_path}")
        return 0
    except StorageError as e:
        print(f"Restore error: {e}", file=sys.stderr)
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="second-brain",
        description="Second Brain - Personal Knowledge System MVP",
    )
    parser.add_argument(
        "--dir", type=str, default=None,
        help="Base directory (default: ~/.second-brain)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_ingest = sub.add_parser("ingest", help="Ingest a file")
    p_ingest.add_argument("file", type=str, help="Path to file")
    p_list = sub.add_parser("list", help="List documents")
    p_list.add_argument("--category", type=str, default=None)
    p_list.add_argument("--status", type=str, default=None)
    p_list.add_argument("--limit", type=int, default=50)
    p_show = sub.add_parser("show", help="Show document details")
    p_show.add_argument("doc_id", type=str)
    p_export = sub.add_parser("export", help="Export document as JSON")
    p_export.add_argument("doc_id", type=str)
    sub.add_parser("export-all", help="Export all documents as JSON")
    sub.add_parser("backup", help="Create database backup")
    p_restore = sub.add_parser("restore", help="Restore from backup")
    p_restore.add_argument("backup_path", type=str)
    args = parser.parse_args(argv)
    config = Config()
    if args.dir:
        config = Config(base_dir=Path(args.dir))
    _setup_logging(config)
    cmd_map = {
        "ingest": _cmd_ingest,
        "list": _cmd_list,
        "show": _cmd_show,
        "export": _cmd_export,
        "export-all": _cmd_export_all,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
    }
    handler = cmd_map[args.command]
    return handler(args, config)


if __name__ == "__main__":
    sys.exit(main())
