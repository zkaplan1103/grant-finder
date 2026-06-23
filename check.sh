#!/usr/bin/env bash
# The gate: lint + tests. Exits non-zero (and says what failed) if anything's red.
# Run before every commit; this is what "all green" means for the project.
set -uo pipefail

fail=0

echo "== ruff =="
ruff check app/ eval/ tests/ scripts/ || fail=1

echo "== pytest =="
python -m pytest tests/ -q || fail=1

if [ "$fail" -ne 0 ]; then
  echo "CHECK FAILED — see above."
  exit 1
fi
echo "ALL GREEN."
