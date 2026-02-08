#!/bin/bash
# Ruff Formatting Check
# Usage:
#   ./scripts/check-format.sh          # Auto-format code
#   ./scripts/check-format.sh --check  # Check only (CI mode)

set -e

CHECK_ONLY=false
if [ "$1" = "--check" ]; then
    CHECK_ONLY=true
fi

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

if [ "$CHECK_ONLY" = true ]; then
    if $PYTHON -m ruff format --check . 2>&1; then
        echo "PASSED: All files formatted correctly"
    else
        echo "FAILED: Some files need formatting"
        echo "Run './scripts/check-format.sh' to auto-fix"
        exit 1
    fi
else
    echo "Auto-formatting code..."
    FORMAT_OUTPUT=$($PYTHON -m ruff format . 2>&1)
    if echo "$FORMAT_OUTPUT" | grep -q "file.*reformatted"; then
        echo "Formatted: $FORMAT_OUTPUT"
    else
        echo "PASSED: All files already formatted"
    fi
fi
