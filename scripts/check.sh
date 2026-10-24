#!/bin/bash
set -e
cd "$(dirname "$0")/.."
echo "=== Syntax check ==="
PYTHONPATH=src python3 -c "import second_brain; print('Import OK')"
echo "=== Tests ==="
PYTHONPATH=src venv/bin/python -m pytest tests/ -q
echo "=== All checks passed ==="
