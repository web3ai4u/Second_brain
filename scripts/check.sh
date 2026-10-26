#!/usr/bin/env bash
set -eu

PYTHONPATH=src python -m pytest tests -q
