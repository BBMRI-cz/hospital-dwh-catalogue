#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# Ruff Linting Check
# Usage:
#   ./scripts/check-lint.sh          # Auto-fix issues
#   ./scripts/check-lint.sh --check  # Check only (CI mode)

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/check-lint.sh [--check]

Options:
  --check   Check only without applying fixes
  --help    Show this message
EOF
}

CHECK_ONLY=false
while [ $# -gt 0 ]; do
    case "$1" in
        --check)
            CHECK_ONLY=true
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

USE_DOCKER_CHECK_RUNNER=false
if should_use_docker_check_runner; then
    USE_DOCKER_CHECK_RUNNER=true
    CHECK_COMMAND=(run_dev_check_compose run --build --rm check python -m ruff check .)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    CHECK_COMMAND=("$PYTHON" -m ruff check .)
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
    if [ "$USE_DOCKER_CHECK_RUNNER" = true ]; then
        run_dev_check_compose run --build --rm check python -m ruff check . --fix 2>&1 || true
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
