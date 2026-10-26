# Second Brain — Personal Knowledge System MVP

Local-first system for ingesting, classifying and storing digital materials with full data provenance.

## What It Does

Second Brain takes your files and text notes, extracts content, classifies them by category, and stores structured records so that:

- Originals are never modified or lost
- Data provenance is transparent — every classification decision recorded with a contract
- Data is portable — export to JSON, restore from backup
- Privacy — everything stored locally, no mandatory external APIs

## Architecture

Three-layer design:

1. Layer A (Generation) — LLM via OpenRouter (optional, falls back to heuristic)
2. Layer B (Decisions) — heuristic classification with decision contract
3. Layer C (Execution) — SQLite WAL, SHA-256, format validation, size limits

## Quick Start

    git clone https://github.com/web3ai4u/Second_brain.git
    cd Second_brain
    python3 -m venv venv
    venv/bin/pip install pytest python-telegram-bot
    PYTHONPATH=src python3 -m second_brain ingest myfile.txt
    PYTHONPATH=src python3 -m second_brain list

## CLI Commands

    ingest <file>        — validate -> extract -> classify -> save
    list [--category C]  — list documents with filters
    show <doc_id>        — show document details
    export <doc_id>      — export as JSON
    export-all           — export all documents
    backup               — create database backup
    restore <path>       — restore from backup

## Telegram Bot

Send text or files to the bot for instant classification and storage.

Bot commands:
    /start  — welcome message
    /list   — recent documents
    /stats  — category statistics
    text    — classified and saved
    file    — extracted, classified, saved

## Classification

Two modes, automatic fallback:

1. LLM (Layer A) — via OpenRouter free models if OPENROUTER_API_KEY is set
2. Heuristic (Layer B) — by file extension + keyword matching
3. Fallback — if LLM fails, heuristic used automatically

Categories: notes, journal, code, finance, data, reference, other

### LLM Setup (Optional)

1. Get free API key at openrouter.ai
2. Add to .env: OPENROUTER_API_KEY=your_key
3. LLM classification used automatically when key is present

Why LLM may not work currently:

OpenRouter free models are community-provided and can be:
- Rate-limited (429 errors during peak usage)
- Removed or renamed (404 errors — model IDs change frequently)
- Temporarily unavailable

When this happens, the system falls back to heuristic classification.
You still get results, just with lower confidence (0.6 vs 0.9).

Alternatives to OpenRouter:
- Ollama on VPS — no API, no limits, needs 2+ GB RAM
- Groq — fast free tier, 30 req/min
- Wait — OpenRouter models may stabilize

## Supported Formats

txt md markdown rst log csv json yaml yml py js html xml

## Testing

    PYTHONPATH=src venv/bin/python -m pytest tests/ -v

32 tests covering: ingestion, extraction, classification, storage, duplicates, audit trail.

## Deployment on VPS

    systemctl enable second-brain-bot
    systemctl start second-brain-bot
    systemctl status second-brain-bot

## Project Structure

    src/second_brain/
      config.py         — Config, Limits, categories, keywords
      models.py         — Document, ExtractedContent, ProcessingEvent
      ingest.py         — file validation, SHA-256, duplicate detection
      extract.py        — text extraction (UTF-8 + Latin-1 fallback)
      classify.py       — heuristic + LLM classification
      storage.py        — SQLite CRUD, export, backup/restore
      llm_client.py     — OpenRouter client with model fallback
      telegram_bot.py   — Telegram bot interface
      cli.py            — CLI with argparse
    tests/              — 32 tests

## License

MIT
