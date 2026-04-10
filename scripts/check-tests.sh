#!/bin/bash
# Test Suite
# Usage: ./scripts/check-tests.sh

set -e

# Detect Python executable
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-catalogue.settings.ci}"

case "$DJANGO_SETTINGS_MODULE" in
    catalogue.settings.ci)
        unset REDIS_URL
        ;;
    catalogue.settings.dev)
        export LOG_DIR="${LOG_DIR:-/tmp/hospital-dwh-catalogue-test-logs}"
        unset REDIS_URL
        mkdir -p "$LOG_DIR"
        ;;
esac

if $PYTHON manage.py test --verbosity 1 2>&1; then
    echo "PASSED: All tests passed"
else
    echo "FAILED: Some tests failed"
    exit 1
fi
