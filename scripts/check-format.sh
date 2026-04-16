#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# Ruff Formatting Check
# Usage:
#   ./scripts/check-format.sh          # Auto-format code
#   ./scripts/check-format.sh --check  # Check only (CI mode)

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/check-format.sh [--check]

Options:
  --check   Check formatting without applying changes
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

if should_use_docker_check_runner; then
    CHECK_COMMAND=(run_dev_check_compose run --build --rm check python -m ruff format --check .)
    FORMAT_COMMAND=(run_dev_check_compose run --build --rm check python -m ruff format .)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    CHECK_COMMAND=("$PYTHON" -m ruff format --check .)
    FORMAT_COMMAND=("$PYTHON" -m ruff format .)
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
