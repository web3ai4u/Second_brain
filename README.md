# Second Brain MVP

Personal Knowledge System - local-first file ingestion, classification and storage.

## Architecture

Three-layer design:
- Layer A (Generation/LLM) - reserved for future
- Layer B (Semantic decisions) - heuristic classification
- Layer C (Deterministic execution) - SQLite, SHA-256, limits

## Pipeline

file -> validate -> extract text -> classify -> save -> verify

Every classification decision is recorded with a contract.

## Usage

  PYTHONPATH=src python3 -m second_brain ingest FILE
  PYTHONPATH=src python3 -m second_brain list
  PYTHONPATH=src python3 -m second_brain show DOC_ID
  PYTHONPATH=src python3 -m second_brain export DOC_ID
  PYTHONPATH=src python3 -m second_brain backup

## Test

  PYTHONPATH=src venv/bin/python -m pytest tests/ -v

## Supported Formats

txt md csv log json yaml yml py js html xml
