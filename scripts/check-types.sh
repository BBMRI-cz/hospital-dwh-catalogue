#!/bin/bash
# Type Checking (mypy)
# Usage: ./scripts/check-types.sh

set -e

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

if $PYTHON -m mypy . 2>&1; then
    echo "PASSED: No type errors"
else
    echo "FAILED: Type errors found (manual fix required)"
    exit 1
fi
