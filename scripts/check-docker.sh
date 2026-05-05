#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
# Docker Build Check
# Usage: ./scripts/check-docker.sh
# Verifies that both runtime and check images build from the compose layout.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

if ! docker_check_runner_available; then
    echo "SKIPPED: Docker compose is unavailable"
    exit 0
fi

if run_dev_check_compose build web check > /dev/null 2>&1; then
    echo "PASSED: Runtime and check images build successfully"
else
    echo "FAILED: Docker compose build failed"
    exit 1
fi
