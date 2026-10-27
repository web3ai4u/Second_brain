# Second Brain — Telegram Personal Intake Agent

Local-first personal knowledge, file ingestion, classification, and action generation system built around Telegram.

This project turns Telegram into a practical intake channel for files, notes, and links. You send a text or upload a file, the system validates and stores it locally, extracts content, classifies it by category, and produces a structured recommendation or next action.

It is designed for real personal workflows:

- upload PDFs, text files, Markdown, CSV, HTML, JSON, and notes
- classify content into categories like notes, journal, code, finance, data, reference, and other
- store provenance and metadata locally in SQLite
- keep a private, portable knowledge base without requiring a cloud-only workflow
- generate suggestions, summaries, and business/learning opportunities from the content
- use Telegram as the front-end for intake and interaction

## What this system does

Second Brain works as a personal knowledge intake agent:

1. Receive a file or text from Telegram
2. Validate the input and reject unsafe/unsupported content
3. Compute a SHA-256 hash and track metadata
4. Store the original locally with provenance
5. Extract readable text from the document
6. Classify the content by type and intent
7. Save the structured record in SQLite
8. Suggest the next action or category of work
9. Keep everything local so it can be exported, backed up, or restored

## Telegram-first workflow

The system is meant to be used in a conversational loop:

- Send text to the bot: notes, ideas, meeting summaries, raw thoughts
- Send a file to the bot: article, PDF, CSV, code, notes, screenshots, or exports
- The bot validates and stores the item
- The bot extracts content and classifies it
- The bot suggests an action: archive, reference, task, article idea, product idea, research note, or next-step list
- You can later query the stored documents from the bot or from the CLI

This makes the project useful as a personal intake layer, not only as a code exercise.

## Architecture

The design is intentionally simple and local-first:

- Telegram bot handles user interaction
- CLI provides direct local ingestion and management
- SQLite stores document metadata, extracted text, events, and process history
- Heuristic classification handles normal operation without external dependencies
- Optional LLM analysis can improve categorization or idea generation when an API key is configured

## Core components

- config.py — runtime configuration, folders, limits, and categories
- models.py — data contracts for documents, extracted content, and processing events
- ingest.py — validation, SHA-256 hash, duplicate detection, file security checks
- extract.py — text extraction for supported formats
- classify.py — category selection and heuristic logic
- storage.py — SQLite CRUD, export, restore, backup
- llm_client.py — optional OpenRouter integration with fallback behavior
- telegram_bot.py — Telegram interaction layer
- cli.py — command-line file intake and document management

## Supported formats

The project supports common text-like files such as:

- txt
- md
- markdown
- rst
- log
- csv
- json
- yaml
- yml
- py
- js
- html
- xml

## Quick start

Clone the project:

```bash
git clone https://github.com/web3ai4u/Second_brain.git
cd Second_brain
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install pytest python-telegram-bot
```

Set the environment if needed:

```bash
cp .env.example .env
```

Then run the CLI:

```bash
PYTHONPATH=src python -m second_brain ingest ./my_note.txt
PYTHONPATH=src python -m second_brain list
PYTHONPATH=src python -m second_brain show <doc_id>
```

Run the bot:

```bash
PYTHONPATH=src python -m second_brain.bot
```

Or use the package entrypoint if it is exposed in your environment:

```bash
PYTHONPATH=src python -m second_brain
```

## Telegram usage flow

1. Start the bot in Telegram
2. Send a text prompt or upload a file
3. The bot validates the input and stores it locally
4. The system extracts text and classifies the content
5. The bot returns a result with category, summary, and suggested next action
6. The content remains available locally for future search, export, and analysis

Typical personal use cases:

- save meeting notes
- capture research snippets
- classify invoices and finance documents
- organize technical notes and code references
- store content for future learning or product inspiration
- keep a private archive of personal knowledge assets

## Bot behavior

The intended bot behavior is:

- text input: store the message, classify it, and record a new item
- file input: validate, ingest, extract, classify, and save locally
- list requests: show recent or paginated intake records
- status/provenance checks: expose document metadata, category, and processing status
- action suggestions: recommend how the material should be organized or used

## Local-first guarantees

This project is intentionally designed to be private and portable:

- no forced cloud dependency for core storage
- all metadata stays local
- all processed documents can be exported as JSON
- database backups and restore flows are supported
- provenance is retained across processing events

## Example scenario

A user sends a PDF of an article and a text note about a product idea:

- article is ingested, extracted, and classified as reference
- note is ingested and classified as idea or journal
- both are stored with timestamps and hashes
- a later summary can pull both into a broader plan or a personal knowledge view
- the user can export everything for backup or migration

## Testing

Run the project tests with:

```bash
PYTHONPATH=src pytest tests/ -v
```

The suite covers:

- ingestion correctness
- extraction behavior
- classification decisions
- storage persistence and database integrity
- duplicate detection
- event auditing
- backup/restore flows

## Project structure

```text
src/second_brain/
  config.py
  models.py
  ingest.py
  extract.py
  classify.py
  storage.py
  llm_client.py
  telegram_bot.py
  cli.py
  __main__.py

tests/
  test_ingest.py
  test_extract.py
  test_classify.py
  test_storage.py
```

## License

MIT

## Why this project matters

The real value is not that it stores files — many tools can do that. The value is in building a personal intake layer that can:

- capture information from real-world sources
- keep a trusted local record
- classify content by meaning
- turn raw material into actionable knowledge
- give you a simple Telegram interface for daily use

This is a practical foundation for a local personal knowledge base, research archive, or file intake agent.
