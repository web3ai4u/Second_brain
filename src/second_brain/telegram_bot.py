from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .classify import classify_document
from .config import Config
from .extract import extract_text
from .ingest import DuplicateFileError, ingest_file
from .storage import Storage

logger = logging.getLogger(__name__)


def _build_storage() -> Storage:
    config = Config()
    config.ensure_dirs()
    storage = Storage(config)
    storage.initialize()
    return storage


def _save_file_to_storage(file_path: Path, config: Config, storage: Storage):
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
    doc.processed_at = datetime.now(timezone.utc).isoformat()
    storage.update_document(doc)
    storage.save_events(classify_events)
    return doc, decision, summary


def _status_reply(doc, decision, summary: str) -> str:
    action_list = decision.action_hints[:2]
    action_text = "; ".join(action_list) if action_list else "No specific action suggested"
    short_summary = (summary or "No summary available").strip()
    if len(short_summary) > 180:
        short_summary = short_summary[:177] + "..."
    return (
        "Saved successfully\n"
        f"ID: {doc.id}\n"
        f"File: {doc.original_filename}\n"
        f"Category: {decision.chosen_category}\n"
        f"Confidence: {decision.confidence:.2f}\n"
        f"Action: {action_text}\n"
        f"Summary: {short_summary}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to Second Brain Bot.\n\n"
        "Send me text or upload a file and I will store it, classify it, and suggest what to do next.\n"
        "Commands: /start /list /stats /help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Usage:\n"
        "- /start: welcome\n"
        "- /list: recent documents\n"
        "- /stats: category summary\n"
        "- Send text: it will be ingested and classified\n"
        "- Send a file: it will be saved and processed"
    )


async def list_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage = _build_storage()
    docs = storage.list_documents(limit=5)
    if not docs:
        await update.message.reply_text("No documents yet.")
        return
    lines = ["Recent documents:"]
    for doc in docs:
        lines.append(f"- {doc.original_filename} [{doc.category or 'unknown'}]")
    await update.message.reply_text("\n".join(lines))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    storage = _build_storage()
    docs = storage.list_documents(limit=1000)
    if not docs:
        await update.message.reply_text("No data yet.")
        return
    counts = {}
    for doc in docs:
        key = doc.category or "other"
        counts[key] = counts.get(key, 0) + 1
    lines = ["Category stats:"]
    for category, count in sorted(counts.items()):
        lines.append(f"- {category}: {count}")
    await update.message.reply_text("\n".join(lines))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("No text received.")
        return
    config = Config(); config.ensure_dirs()
    storage = Storage(config)
    storage.initialize()
    temp_path = Path(tempfile.gettempdir()) / f"telegram_text_{uuid.uuid4().hex}.txt"
    temp_path.write_text(text, encoding="utf-8")
    try:
        doc, decision, summary = _save_file_to_storage(temp_path, config, storage)
    except DuplicateFileError:
        await update.message.reply_text("This text was already saved earlier as a duplicate.")
        return
    except Exception as exc:  # pragma: no cover - bot-level safety
        logger.exception("Text processing failed")
        await update.message.reply_text(f"Processing failed: {exc}")
        return
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    await update.message.reply_text(_status_reply(doc, decision, summary))


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    file = message.document or message.photo[-1] if message.photo else None
    if file is None:
        await update.message.reply_text("No file received.")
        return
    config = Config(); config.ensure_dirs()
    storage = Storage(config)
    storage.initialize()
    telegram_file = await context.bot.get_file(file.file_id)
    filename = file.file_name or f"telegram_{uuid.uuid4().hex}.bin"
    temp_path = Path(tempfile.gettempdir()) / f"telegram_upload_{uuid.uuid4().hex}_{filename}"
    await telegram_file.download_to_drive(custom_path=str(temp_path))
    try:
        doc, decision, summary = _save_file_to_storage(temp_path, config, storage)
    except DuplicateFileError:
        await update.message.reply_text("This file was already saved earlier as a duplicate.")
        return
    except Exception as exc:  # pragma: no cover - bot-level safety
        logger.exception("File processing failed")
        await update.message.reply_text(f"Processing failed: {exc}")
        return
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
    await update.message.reply_text(_status_reply(doc, decision, summary))


async def run_bot(token: str | None = None) -> None:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Export it before running the bot.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_recent))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ATTACHMENT, handle_file))

    logger.info("Starting Second Brain Telegram bot")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    main()


__all__ = ["run_bot", "main"]
