#!/usr/bin/env bash
# Local pre-push gate: lint, format, types, and offline tests.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check .
ruff format --check .
mypy
pytest
