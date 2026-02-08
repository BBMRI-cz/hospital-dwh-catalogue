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

if DJANGO_SETTINGS_MODULE=catalogue.settings.test $PYTHON manage.py test --verbosity 1 2>&1; then
    echo "PASSED: All tests passed"
else
    echo "FAILED: Some tests failed"
    exit 1
fi
