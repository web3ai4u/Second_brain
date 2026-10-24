# Architecture

## Three-Layer Design

- Layer A (Generation/LLM) - reserved for future LLM integration
- Layer B (Semantic decisions) - heuristic classification by extension + keywords
- Layer C (Deterministic execution) - SQLite WAL, SHA-256, size limits

## Processing Pipeline

1. Ingest: validate file, compute SHA-256, detect duplicates
2. Extract: read text (UTF-8 with Latin-1 fallback), enforce size limit
3. Classify: heuristic category assignment with confidence score
4. Save: persist to SQLite with audit trail
5. Verify: every decision recorded in ClassificationDecision contract

## Data Provenance

Every record includes SHA-256 hash, processing events, and classification contract.
