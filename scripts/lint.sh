#!/bin/bash
# =============================================================================
# Code Quality Script - Auto-fix and Check
# =============================================================================
# This script will:
# 1. Auto-fix all issues that can be fixed automatically
# 2. Show only issues that require manual intervention
# 3. Run the test suite
# 
# Usage:
#   ./scripts/lint.sh          # Run all checks with auto-fix
#   ./scripts/lint.sh --check  # Check only, no auto-fix (used in CI)
# =============================================================================

set -e

# Parse arguments
CHECK_ONLY=false
if [ "$1" = "--check" ]; then
    CHECK_ONLY=true
fi

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

# -----------------------------------------------------------------------------
# Step 1: Ruff Linting
# -----------------------------------------------------------------------------
echo "[1/5] Ruff Linting"
echo "----------------------------------------"

if [ "$CHECK_ONLY" = true ]; then
    if $PYTHON -m ruff check . 2>&1; then
        echo "PASSED: No linting issues"
    else
        echo "FAILED: Linting errors found"
        FAILED=true
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
        FAILED=true
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: Ruff Formatting
# -----------------------------------------------------------------------------
echo "[2/5] Code Formatting"
echo "----------------------------------------"

if [ "$CHECK_ONLY" = true ]; then
    if $PYTHON -m ruff format --check . 2>&1; then
        echo "PASSED: All files formatted correctly"
    else
        echo "FAILED: Some files need formatting"
        echo "Run './scripts/lint.sh' to auto-fix"
        FAILED=true
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
echo ""

# -----------------------------------------------------------------------------
# Step 3: Type Checking (mypy)
# -----------------------------------------------------------------------------
echo "[3/5] Type Checking (mypy)"
echo "----------------------------------------"

if $PYTHON -m mypy . 2>&1; then
    echo "PASSED: No type errors"
else
    echo "FAILED: Type errors found (manual fix required)"
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 4: Security Check (bandit)
# -----------------------------------------------------------------------------
echo "[4/5] Security Check (bandit)"
echo "----------------------------------------"

BANDIT_OUTPUT=$($PYTHON -m bandit -r . -x ./warehouse/static,./venv,./.venv,./node_modules -ll 2>&1) || true
if echo "$BANDIT_OUTPUT" | grep -q "No issues identified"; then
    echo "PASSED: No security issues"
elif echo "$BANDIT_OUTPUT" | grep -q "Severity: Medium\|Severity: High"; then
    echo "FAILED: Security issues found (manual fix required)"
    echo ""
    echo "$BANDIT_OUTPUT" | grep -A5 "Issue:" || true
    FAILED=true
else
    echo "PASSED: No medium/high severity issues"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 5: Tests
# -----------------------------------------------------------------------------
echo "[5/5] Tests"
echo "----------------------------------------"

if DJANGO_SETTINGS_MODULE=catalogue.settings.test $PYTHON manage.py test --verbosity 1 2>&1; then
    echo "PASSED: All tests passed"
else
    echo "FAILED: Some tests failed"
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
