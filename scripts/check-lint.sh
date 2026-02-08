#!/bin/bash
# Ruff Linting Check
# Usage:
#   ./scripts/check-lint.sh          # Auto-fix issues
#   ./scripts/check-lint.sh --check  # Check only (CI mode)

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
    if $PYTHON -m ruff check . 2>&1; then
        echo "PASSED: No linting issues"
    else
        echo "FAILED: Linting errors found"
        exit 1
    fi
else
    echo "Auto-fixing linting issues..."
    $PYTHON -m ruff check . --fix 2>&1 || true
    
    if $PYTHON -m ruff check . 2>&1; then
        echo "PASSED: Linting complete (auto-fixed where possible)"
    else
        echo ""
        echo "ISSUES REQUIRING MANUAL FIX:"
        $PYTHON -m ruff check . 2>&1 || true
        exit 1
    fi
fi
