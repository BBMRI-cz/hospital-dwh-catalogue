#!/bin/bash
# =============================================================================
# Code Quality Script - Auto-fix and Check
# =============================================================================
# This script will:
# 1. Auto-fix all issues that can be fixed automatically
# 2. Show only issues that require manual intervention
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
echo "[1/4] Ruff Linting"
echo "----------------------------------------"

if [ "$CHECK_ONLY" = true ]; then
    if ruff check . 2>&1; then
        echo "PASSED: No linting issues"
    else
        echo "FAILED: Linting errors found"
        FAILED=true
    fi
else
    echo "Auto-fixing linting issues..."
    ruff check . --fix 2>&1 || true
    
    if ruff check . 2>&1; then
        echo "PASSED: Linting complete (auto-fixed where possible)"
    else
        echo ""
        echo "ISSUES REQUIRING MANUAL FIX:"
        ruff check . 2>&1 || true
        FAILED=true
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: Ruff Formatting
# -----------------------------------------------------------------------------
echo "[2/4] Code Formatting"
echo "----------------------------------------"

if [ "$CHECK_ONLY" = true ]; then
    if ruff format --check . 2>&1; then
        echo "PASSED: All files formatted correctly"
    else
        echo "FAILED: Some files need formatting"
        echo "Run './scripts/lint.sh' to auto-fix"
        FAILED=true
    fi
else
    echo "Auto-formatting code..."
    FORMAT_OUTPUT=$(ruff format . 2>&1)
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
echo "[3/4] Type Checking (mypy)"
echo "----------------------------------------"

if mypy . 2>&1; then
    echo "PASSED: No type errors"
else
    echo "FAILED: Type errors found (manual fix required)"
    FAILED=true
fi
echo ""

# -----------------------------------------------------------------------------
# Step 4: Security Check (bandit)
# -----------------------------------------------------------------------------
echo "[4/4] Security Check (bandit)"
echo "----------------------------------------"

BANDIT_OUTPUT=$(bandit -r . -x ./warehouse/static,./venv,./.venv,./node_modules -ll 2>&1) || true
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
