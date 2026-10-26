# Implementation plan

## Stage 0 — audit and constraints

- Confirm repository access and branch state.
- Review existing project files and tests.
- Identify unsupported or partially implemented assumptions.
- Record explicit limitations and avoid unverified claims.

## Stage 1 — verified MVP

- configure a local workspace directory
- ingest a single text file
- hash and duplicate-check it
- extract text
- classify with deterministic fallback logic
- store document, content and processing events
- export JSON and create a backup

## Stage 2 — error handling and safety

- path traversal checks
- invalid format handling
- empty/oversized file handling
- backup restore checks
- log hygiene

## Stage 3 — optional extension

- PDF and DOCX adapters
- OCR evaluation only if explicitly needed
- Telegram or web UI only after basic CLI MVP proves stable

## Stage 4 — longer-term memory

- confirm facts and provenance
- support search and metadata filtering
- consider semantics only after the base document archive is stable
