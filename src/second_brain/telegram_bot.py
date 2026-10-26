"""Telegram bot for Second Brain.

Accepts text messages and files, classifies and stores them.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from .config import Config
from .ingest import ingest_file, IngestError, DuplicateFileError
from .extract import extract_text, ExtractionError
from .classify import classify_document
from .storage import Storage, StorageError
from .models import Document

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Second Brain Bot\n\n"
    "Send me text or a file and I will:\n"
    "1. Extract content\n"
    "2. Classify it\n"
    "3. Store in knowledge base\n\n"
    "Commands:\n"
    "/list - show recent documents\n"
    "/stats - show statistics\n"
    "/help - this message"
)


def _setup_dependencies(config: Config):
    storage = Storage(config)
    storage.initialize()
    return storage


def _process_text(text: str, config: Config, storage: Storage) -> str:
    from datetime import datetime, timezone
    from .models import ExtractedContent
    import uuid

    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = Document(
        id=doc_id,
        original_filename="message.txt",
        detected_format="text",
        file_size=len(text.encode("utf-8")),
        sha256=import_hashlib_sha256(text.encode("utf-8")),
        source_path="telegram://message",
        created_at=now,
        processing_status="processing",
        extraction_status="pending",
    )

    try:
        storage.save_document(doc)
    except StorageError:
        return "Error: failed to save document"

    content = ExtractedContent(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        extracted_text=text[:10000],
        extraction_method="telegram_text",
        extraction_version="1.0",
        created_at=now,
    )
    storage.save_extracted_content(content)

    decision, summary, events = classify_document(doc, content)
    doc.category = decision.chosen_category
    doc.summary = summary
    doc.processing_status = "completed"
    doc.extraction_status = "completed"
    doc.processed_at = datetime.now(timezone.utc).isoformat()
    storage.update_document(doc)
    storage.save_events(events)

    review = ""
    if decision.requires_manual_review:
        review = f"\nReview: {decision.manual_review_reason}"

    return (
        f"Saved!\n"
        f"Category: {doc.category} ({decision.confidence:.0%})\n"
        f"Summary: {summary[:200]}{review}"
    )


def _process_file(file_path: Path, config: Config, storage: Storage) -> str:
    try:
        doc, ingest_events = ingest_file(file_path, config)
    except DuplicateFileError:
        return "Duplicate: file already exists"
    except IngestError as e:
        return f"Error: {e}"

    doc.processing_status = "processing"
    storage.save_document(doc)
    storage.save_events(ingest_events)

    try:
        content, extract_events = extract_text(doc, config)
    except ExtractionError as e:
        return f"Extraction error: {e}"

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

    review = ""
    if decision.requires_manual_review:
        review = f"\nReview: {decision.manual_review_reason}"

    return (
        f"File saved: {doc.original_filename}\n"
        f"Category: {doc.category} ({decision.confidence:.0%})\n"
        f"Summary: {summary[:200]}{review}"
    )


def import_hashlib_sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run_bot(config: Config, token: str):
    try:
        from telegram import Update, Bot
        from telegram.ext import (
            ApplicationBuilder,
            CommandHandler,
            MessageHandler,
            filters,
            ContextTypes,
        )
    except ImportError:
        print("Error: python-telegram-bot not installed")
        print("Run: venv/bin/pip install python-telegram-bot")
        return

    storage = _setup_dependencies(config)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(HELP_TEXT)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(HELP_TEXT)

    async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        docs = storage.list_documents(limit=10)
        if not docs:
            await update.message.reply_text("No documents yet.")
            return
        lines = []
        for doc in docs:
            cat = doc.category or "?"
            lines.append(f"- {doc.original_filename} [{cat}]")
        await update.message.reply_text("Recent documents:\n" + "\n".join(lines))

    async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        docs = storage.list_documents(limit=10000)
        cats = {}
        for doc in docs:
            c = doc.category or "other"
            cats[c] = cats.get(c, 0) + 1
        lines = [f"Total: {len(docs)}"]
        for c, n in sorted(cats.items()):
            lines.append(f"  {c}: {n}")
        await update.message.reply_text("\n".join(lines))

    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        result = _process_text(text, config, storage)
        await update.message.reply_text(result)

    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
        doc_file = update.message.document
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / doc_file.file_name
            bot = context.bot
            await bot.download_file(doc_file.file_id, str(file_path))
            result = _process_file(file_path, config, storage)
            await update.message.reply_text(result)

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Second Brain bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        exit(1)
    config = Config()
    run_bot(config, token)
