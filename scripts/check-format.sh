#!/bin/bash
# Ruff Formatting Check
# Usage:
#   ./scripts/check-format.sh          # Auto-format code
#   ./scripts/check-format.sh --check  # Check only (CI mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if should_use_docker_check_runner; then
    CHECK_COMMAND=(run_dev_check_compose run --rm check python -m ruff format --check .)
    FORMAT_COMMAND=(run_dev_check_compose run --rm check python -m ruff format .)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    CHECK_COMMAND=("$PYTHON" -m ruff format --check .)
    FORMAT_COMMAND=("$PYTHON" -m ruff format .)
fi

CHECK_ONLY=false
if [ "$1" = "--check" ]; then
    CHECK_ONLY=true
fi

if [ "$CHECK_ONLY" = true ]; then
    if "${CHECK_COMMAND[@]}" 2>&1; then
        echo "PASSED: All files formatted correctly"
    else
        echo "FAILED: Some files need formatting"
        echo "Run './scripts/check-format.sh' to auto-fix"
        exit 1
    fi
else
    echo "Auto-formatting code..."
    FORMAT_OUTPUT=$("${FORMAT_COMMAND[@]}" 2>&1)
    if echo "$FORMAT_OUTPUT" | grep -q "file.*reformatted"; then
        echo "Formatted: $FORMAT_OUTPUT"
    else
        echo "PASSED: All files already formatted"
    fi
fi
