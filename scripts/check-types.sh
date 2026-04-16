#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# Type Checking (mypy)
# Usage: ./scripts/check-types.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if should_use_docker_check_runner; then
    CHECK_COMMAND=(run_dev_check_compose run --build --rm check python -m mypy .)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    CHECK_COMMAND=("$PYTHON" -m mypy .)
fi

if "${CHECK_COMMAND[@]}" 2>&1; then
    echo "PASSED: No type errors"
else
    echo "FAILED: Type errors found (manual fix required)"
    exit 1
fi
