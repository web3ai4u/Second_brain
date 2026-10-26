# Architecture

## Overview

Second Brain is intentionally built as a compact, local-first knowledge ingestion system. The MVP proves one end-to-end flow: a user selects a local file, the system validates it, extracts text, classifies it, stores metadata and provenance, and exports the result for review.

## Layer A — generation and interpretation

The project keeps this layer optional and deliberately narrow. If an LLM is configured, it may suggest a category or summary. However, the system never relies on an external model for deterministic operations such as hashing, path validation, duplicate detection or schema checks.

Current implementation:
- optional OpenRouter client in `src/second_brain/llm_client.py`
- fallback to deterministic heuristics when no API key, no network or invalid model response is returned

## Layer B — semantic decisions

This project uses lightweight, explicit heuristics as the default decision layer. Category selection is based on file extension and keyword matches, not on opaque black-box behavior.

Key file:
- `src/second_brain/classify.py`

The decision contract is stored in the classification result, including:
- allowed categories
- selected category
- confidence
- criteria used
- manual review flag

## Layer C — deterministic execution

This layer is the real source of trust for the MVP. It includes:
- file validation and size limits
- SHA-256 hashing
- duplicate detection
- local copy of the original file
- SQLite persistence
- JSON export and backup/restore
- processing event logging

Key files:
- `src/second_brain/config.py`
- `src/second_brain/ingest.py`
- `src/second_brain/extract.py`
- `src/second_brain/storage.py`

## Safety notes

- No code is executed from uploaded documents.
- Document content is treated as data, not instructions.
- Secrets are never stored in project files or logs.
- All writes remain local unless the user explicitly opts into an external API.

## Future extension boundaries

The project is structured so that later stages can add OCR, PDF support, archive inspection, semantic indexing and UI wrappers without rewriting the core ingestion model.
