from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from .classify import classify_document, suggest_action
from .config import Config
from .extract import ExtractionError, extract_text
from .ingest import (
    DuplicateFileError,
    EmptyFileError,
    FileTooLargeError,
    IngestError,
    UnsupportedFormatError,
    ingest_file,
)
from .storage import Storage, StorageError


logger = logging.getLogger(__name__)


def _process_file(file_path: Path, config: Config, storage: Storage) -> dict:
    doc, ingest_events = ingest_file(file_path, config)
    doc.processing_status = "processing"
    storage.save_document(doc)
    storage.save_events(ingest_events)

    content, extract_events = extract_text(doc, config)
    doc.extraction_status = "completed"
    storage.save_extracted_content(content)
    storage.save_events(extract_events)

    decision, summary, classify_events = classify_document(doc, content)
    doc.category = decision.chosen_category
    doc.summary = summary
    doc.action_hint = "; ".join(decision.action_hints) if decision.action_hints else None
    doc.processing_status = "completed"
    from datetime import datetime, timezone
    doc.processed_at = datetime.now(timezone.utc).isoformat()
    storage.update_document(doc)
    storage.save_events(classify_events)

    return {
        "doc_id": doc.id,
        "filename": doc.original_filename,
        "category": doc.category,
        "action_hint": doc.action_hint,
        "summary": summary,
        "confidence": decision.confidence,
    }


def _cmd_ingest(args, config):
    storage = Storage(config)
    storage.initialize()
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 1
    try:
        result = _process_file(file_path, config, storage)
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
    except ExtractionError as e:
        print(f"Extraction error: {e}", file=sys.stderr)
        return 1

    print("Document ingested successfully!")
    print(f"  ID:       {result['doc_id']}")
    print(f"  File:     {result['filename']}")
    print(f"  Category: {result['category']}")
    print(f"  Action:   {result['action_hint']}")
    print(f"  Summary:  {result['summary']}")
    return 0


def _cmd_list(args, config):
    storage = Storage(config)
    storage.initialize()
    docs = storage.list_documents(category=args.category, status=args.status, limit=args.limit)
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


def _cmd_watch(args, config):
    storage = Storage(config)
    storage.initialize()
    inbox = Path(args.directory or config.inbox_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"Watching inbox: {inbox} (ctrl-c to stop)")
    try:
        while True:
            for item in sorted(inbox.iterdir()):
                if item.is_file() and not item.name.startswith("."):
                    try:
                        result = _process_file(item, config, storage)
                        print(f"Processed {item.name}: {result['category']} -> {result['action_hint']}")
                    except Exception as exc:
                        print(f"Skip {item.name}: {exc}", file=sys.stderr)
                    finally:
                        try:
                            item.unlink(missing_ok=True)
                        except OSError:
                            pass
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")
        return 0


def _cmd_suggest(args, config):
    if not args.file:
        print("Provide a text file or file path to suggest action for.", file=sys.stderr)
        return 1
    text = Path(args.file).read_text(encoding="utf-8", errors="ignore")
    from .classify import _classify_by_extension, _classify_by_keywords
    doc = type("D", (), {"original_filename": Path(args.file).name})()
    cat, _, _ = _classify_by_keywords(text)
    if cat is None:
        cat = _classify_by_extension(doc.original_filename) or "other"
    actions = suggest_action(cat)
    print(f"Suggested category: {cat}")
    for action in actions:
        print(f"- {action}")
    return 0


def _cmd_bot(args, config):
    from .telegram_bot import run_bot
    return asyncio.run(run_bot(args.token))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="second-brain",
        description="Local file intake agent for organizing, storing and understanding files.",
    )
    parser.add_argument("--dir", type=str, default=None, help="Base directory (default: ~/.second-brain)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a single file")
    p_ingest.add_argument("file", type=str)

    p_list = sub.add_parser("list", help="List stored documents")
    p_list.add_argument("--category", type=str, default=None)
    p_list.add_argument("--status", type=str, default=None)
    p_list.add_argument("--limit", type=int, default=50)

    p_show = sub.add_parser("show", help="Show a document")
    p_show.add_argument("doc_id", type=str)

    p_export = sub.add_parser("export", help="Export a document")
    p_export.add_argument("doc_id", type=str)

    sub.add_parser("export-all", help="Export all documents")
    sub.add_parser("backup", help="Create a database backup")

    p_restore = sub.add_parser("restore", help="Restore from backup")
    p_restore.add_argument("backup_path", type=str)

    p_watch = sub.add_parser("watch", help="Watch an inbox folder and process incoming files")
    p_watch.add_argument("directory", type=str, nargs="?", default=None)
    p_watch.add_argument("--interval", type=float, default=2.0)

    p_suggest = sub.add_parser("suggest", help="Suggest category and action for a file")
    p_suggest.add_argument("file", type=str)

    p_bot = sub.add_parser("bot", help="Run the Telegram bot")
    p_bot.add_argument("--token", type=str, default=None)

    args = parser.parse_args(argv)
    config = Config()
    if args.dir:
        config = Config(base_dir=Path(args.dir))
    config.ensure_dirs()

    cmd_map = {
        "ingest": _cmd_ingest,
        "list": _cmd_list,
        "show": _cmd_show,
        "export": _cmd_export,
        "export-all": _cmd_export_all,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
        "watch": _cmd_watch,
        "suggest": _cmd_suggest,
        "bot": _cmd_bot,
    }
    return cmd_map[args.command](args, config)


if __name__ == "__main__":
    sys.exit(main())
