# OPER.FILE.md

Purpose: build and verify a local-first Second Brain MVP without introducing hidden costs, secret leakage, or untested claims.

## 1. Scope

Files in scope for this pass:
- src/second_brain/config.py
- src/second_brain/ingest.py
- src/second_brain/extract.py
- src/second_brain/classify.py
- src/second_brain/storage.py
- src/second_brain/cli.py
- tests/*.py
- README.md
- docs/*.md
- SECURITY.md

## 2. Rules

- Keep all data local by default.
- Never commit tokens or secrets.
- Do not publish private archives or exports.
- Only implement the minimal path that proves the MVP scenario.
- Prefer deterministic logic over probabilistic behavior.
- If a check cannot run in this environment, mark it as NOT RUN.

## 3. Minimal execution plan

1. Audit repo structure, files and existing tests.
2. Fix deterministic ingest, validation and path-safety issues.
3. Confirm extraction and classification pipeline still work.
4. Preserve original files and audit events.
5. Run available verification commands.
6. Record actual results and any unresolved issues.

## 4. Verification step

When validation is possible, run:

```bash
PYTHONPATH=src pytest tests -q
```

If the environment prevents execution, report:

- check name
- command attempted
- reason for failure to run
- status: NOT RUN

## 5. Stop condition

Stop after the minimal validated scenario is in place and the repository contains honest documentation about current limits.
