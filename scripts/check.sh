#!/bin/bash
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

set -e

# Parse arguments
CHECK_ONLY=false
if [ "$1" = "--check" ]; then
    CHECK_ONLY=true
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Setup virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    PIP=".venv/bin/pip"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
    PIP="venv/bin/pip"
else
    PYTHON="python"
    PIP="pip"
fi

# Install/upgrade dependencies if needed
if [ ! -f ".venv/.deps_installed" ] || [ "requirements.txt" -nt ".venv/.deps_installed" ] || [ "requirements-dev.txt" -nt ".venv/.deps_installed" ]; then
    echo "Installing/updating dependencies..."
    $PIP install --upgrade pip > /dev/null 2>&1
    $PIP install -r requirements.txt > /dev/null 2>&1
    $PIP install -r requirements-dev.txt > /dev/null 2>&1
    touch .venv/.deps_installed
    echo "Dependencies installed successfully"
    echo ""
fi

# Track if any check fails
FAILED=false

echo ""
echo "========================================"
echo "Hospital DWH Catalogue - Code Quality"
echo "========================================"
echo ""

# Pass --check flag to scripts that support it
CHECK_FLAG=""
if [ "$CHECK_ONLY" = true ]; then
    CHECK_FLAG="--check"
fi

# -----------------------------------------------------------------------------
# Step 1: Ruff Linting
# -----------------------------------------------------------------------------
echo "[1/6] Ruff Linting"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-lint.sh" $CHECK_FLAG; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: Ruff Formatting
# -----------------------------------------------------------------------------
echo "[2/6] Code Formatting"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-format.sh" $CHECK_FLAG; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 3: Type Checking (mypy)
# -----------------------------------------------------------------------------
echo "[3/6] Type Checking (mypy)"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-types.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 4: Security Check (bandit)
# -----------------------------------------------------------------------------
echo "[4/6] Security Check (bandit)"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-security.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 5: Translation Check
# -----------------------------------------------------------------------------
echo "[5/6] Translation Check"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-translations.sh"; then
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 6: Tests
# -----------------------------------------------------------------------------
echo "[6/6] Tests"
echo "----------------------------------------"
if ! "$SCRIPT_DIR/check-tests.sh"; then
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

