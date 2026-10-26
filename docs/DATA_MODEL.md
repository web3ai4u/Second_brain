# Data model

## Core tables

### documents

Stores the canonical record for each ingested file.

Fields:
- id
- original_filename
- detected_format
- file_size
- sha256
- source_path
- created_at
- processed_at
- processing_status
- extraction_status
- category
- summary
- metadata_json

### extracted_content

Stores the text extracted from the original file.

Fields:
- id
- document_id
- extracted_text
- extraction_method
- extraction_version
- created_at

### processing_events

Stores the audit trail for each processing operation.

Fields:
- id
- document_id
- timestamp
- component
- operation
- status
- error_type
- sanitized_message
- run_id

## Separation of concerns

The design deliberately distinguishes between:
- original material
- extracted text
- model-generated summary/classification
- processing events
- final user-approved record

This reduces the risk of silently conflating input, inference and verified metadata.

## Current scope

This MVP does not yet add a long-term facts table or a graph layer. Those should only be introduced once the base archival workflow is proven in real usage.
