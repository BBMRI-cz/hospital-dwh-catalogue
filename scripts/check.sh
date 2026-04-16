#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# =============================================================================
# Code Quality Script - Master Orchestrator
# =============================================================================
# This script runs all code quality checks by calling individual check scripts:
# 1. Linting (Ruff) - Auto-fixable
# 2. Code formatting (Ruff) - Auto-fixable
# 3. Type checking (mypy) - Manual fixes required
# 4. Security scanning (Bandit) - Manual fixes required
# 5. Translation completeness - Manual fixes required
# 6. Test suite
# 7. Docker build check
# 
# Usage:
#   ./scripts/check.sh          # Run all checks with auto-fix
#   ./scripts/check.sh --check  # Check only, no auto-fix (used in CI)
# 
# Individual checks can also be run separately:
#   ./scripts/check-lint.sh
#   ./scripts/check-format.sh
#   ./scripts/check-types.sh
#   ./scripts/check-security.sh
#   ./scripts/check-translations.sh
#   ./scripts/check-tests.sh
# =============================================================================

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/check.sh [--check]

Runs the full quality suite.

Options:
  --check   Run in check-only mode (used in CI)
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

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if should_use_docker_check_runner; then
    echo "Using Docker check runner because local dev tools are unavailable."
    echo ""
else
    ensure_project_dependencies
fi

# Track if any check fails
FAILED=false

echo ""
echo "========================================"
echo "Hospital DWH Catalogue - Code Quality"
echo "========================================"
echo ""

# Pass --check flag to scripts that support it
CHECK_ARGS=()
if [ "$CHECK_ONLY" = true ]; then
    CHECK_ARGS+=(--check)
fi

# -----------------------------------------------------------------------------
# Step 1: Ruff Linting
# -----------------------------------------------------------------------------
echo "[1/7] Ruff Linting"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-lint.sh" "${CHECK_ARGS[@]}"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: Ruff Formatting
# -----------------------------------------------------------------------------
echo "[2/7] Code Formatting"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-format.sh" "${CHECK_ARGS[@]}"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 3: Type Checking (mypy)
# -----------------------------------------------------------------------------
echo "[3/7] Type Checking (mypy)"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-types.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 4: Security Check (bandit)
# -----------------------------------------------------------------------------
echo "[4/7] Security Check (bandit)"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-security.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 5: Translation Check
# -----------------------------------------------------------------------------
echo "[5/7] Translation Check (completeness + compiled)"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-translations.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 6: Tests
# -----------------------------------------------------------------------------
echo "[6/7] Tests"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-tests.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 7: Docker Build
# -----------------------------------------------------------------------------
echo "[7/7] Docker Build"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-docker.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo "========================================"
if [ "$FAILED" = true ]; then
    echo "FAILED: Some checks did not pass"
    echo ""
    echo "Please fix the issues listed above."
    echo "========================================"
    exit 1
else
    echo "PASSED: All checks successful"
    echo ""
    echo "Code is ready for commit."
    echo "========================================"
    exit 0
fi
