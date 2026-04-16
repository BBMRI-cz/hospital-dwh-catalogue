#!/bin/bash
# Security Check (bandit)
# Usage: ./scripts/check-security.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

SCAN_TARGETS=(
    manage.py
    catalogue
    schema_registry
    fair_genomes
    frontend
    ticketing
    shared
    warehouse
    scripts
    docker/startup.py
    docker/startup_tasks.py
)

if should_use_docker_check_runner; then
    BANDIT_COMMAND=(run_dev_check_compose run --build --rm check python -m bandit -r "${SCAN_TARGETS[@]}" -x ./warehouse/static,./venv,./.venv,./node_modules -ll)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    BANDIT_COMMAND=("$PYTHON" -m bandit -r "${SCAN_TARGETS[@]}" -x ./warehouse/static,./venv,./.venv,./node_modules -ll)
fi

BANDIT_OUTPUT=$("${BANDIT_COMMAND[@]}" 2>&1) || true
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
