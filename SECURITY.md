# Security and privacy policy

## Local-first principle

Second Brain is designed to work on the user machine without requiring mandatory cloud storage, paid services, or external infrastructure.

## Data handling

- originals are copied into a local workspace directory
- hashes are computed to detect duplicates
- extracted text is kept in SQLite, not in a remote system
- exports remain local JSON files until the user chooses otherwise

## Input validation

- file existence and type are checked
- empty files are rejected
- oversized files are rejected
- filename length is limited
- path traversal is blocked by validating all file paths against the trusted workspace root

## External model usage

Optional LLM-based classification is disabled by default. If a user enables it, the code should only send the minimum necessary text for classification and never transmit secrets or sensitive material by default.

## Secret handling

- do not store real tokens in the repository
- do not add private archives to git
- use `.env.example` only for examples
- do not log full secrets, API keys or internal file paths that may reveal private content

## Backup rules

Backups are local SQLite copies and are only considered verified after a restore test. This project does not treat backups as proof of integrity without recovery validation.
