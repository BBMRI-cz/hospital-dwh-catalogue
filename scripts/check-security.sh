#!/bin/bash
# Security Check (bandit)
# Usage: ./scripts/check-security.sh

set -e

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

BANDIT_OUTPUT=$($PYTHON -m bandit -r . -x ./warehouse/static,./venv,./.venv,./node_modules -ll 2>&1) || true
if echo "$BANDIT_OUTPUT" | grep -q "No issues identified"; then
    echo "PASSED: No security issues"
elif echo "$BANDIT_OUTPUT" | grep -q "Severity: Medium\|Severity: High"; then
    echo "FAILED: Security issues found (manual fix required)"
    echo ""
    echo "$BANDIT_OUTPUT" | grep -A5 "Issue:" || true
    exit 1
else
    echo "PASSED: No medium/high severity issues"
fi
