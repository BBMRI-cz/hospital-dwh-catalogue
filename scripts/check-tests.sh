#!/bin/bash
# Test Suite
# Usage: ./scripts/check-tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

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

if should_use_docker_check_runner; then
    TEST_COMMAND=(run_dev_check_compose run --build --rm -e "DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE" check python manage.py test --verbosity 1)
else
    ensure_project_dependencies
    PYTHON="$(resolve_python)"
    TEST_COMMAND=("$PYTHON" "manage.py" "test" "--verbosity" "1")
fi

if "${TEST_COMMAND[@]}" 2>&1; then
    echo "PASSED: All tests passed"
else
    echo "FAILED: Some tests failed"
    exit 1
fi
