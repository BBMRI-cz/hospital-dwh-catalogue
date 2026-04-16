#!/bin/bash
# Ruff Linting Check
# Usage:
#   ./scripts/check-lint.sh          # Auto-fix issues
#   ./scripts/check-lint.sh --check  # Check only (CI mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if should_use_docker_check_runner; then
    CHECK_COMMAND=(run_dev_check_compose run --rm check python -m ruff check .)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    CHECK_COMMAND=("$PYTHON" -m ruff check .)
fi

CHECK_ONLY=false
if [ "$1" = "--check" ]; then
    CHECK_ONLY=true
fi

if [ "$CHECK_ONLY" = true ]; then
    if "${CHECK_COMMAND[@]}" 2>&1; then
        echo "PASSED: No linting issues"
    else
        echo "FAILED: Linting errors found"
        exit 1
    fi
else
    echo "Auto-fixing linting issues..."
    if should_use_docker_check_runner; then
        run_dev_check_compose run --rm check python -m ruff check . --fix 2>&1 || true
    else
        "$PYTHON" -m ruff check . --fix 2>&1 || true
    fi
    
    if "${CHECK_COMMAND[@]}" 2>&1; then
        echo "PASSED: Linting complete (auto-fixed where possible)"
    else
        echo ""
        echo "ISSUES REQUIRING MANUAL FIX:"
        "${CHECK_COMMAND[@]}" 2>&1 || true
        exit 1
    fi
fi
