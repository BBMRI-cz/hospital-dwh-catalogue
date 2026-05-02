#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/scripts/lib/common.sh"
# shellcheck source=scripts/lib/deploy_contract.sh
source "$SCRIPT_DIR/scripts/lib/deploy_contract.sh"

WITH_OBSERVABILITY=false

usage() {
    cat <<'EOF'
Usage: ./deploy.sh [--with-observability]

Reads DEPLOY_ENV from .env, validates the environment contract,
and starts the matching Docker Compose stack.

Use --with-observability to include Loki, Promtail, and Grafana for
dev or staging. Production always includes the observability stack.
EOF
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --with-observability)
                WITH_OBSERVABILITY=true
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
}

enable_environment_defaults() {
    if [ "$DEPLOY_ENV" = "prod" ]; then
        WITH_OBSERVABILITY=true
    fi
}

run_compose() {
    local args=()

    if [ "$WITH_OBSERVABILITY" = true ]; then
        args+=(--with-observability)
    fi

    "$SCRIPT_DIR/scripts/compose.sh" "${args[@]}" "$@"
}

print_deploy_summary() {
    echo "Target environment: $DEPLOY_ENV"

    if [ "$DEPLOY_ENV" = "prod" ]; then
        echo "Observability: always-on in prod"
    elif [ "$WITH_OBSERVABILITY" = true ]; then
        echo "Observability: enabled"
    else
        echo "Observability: disabled"
    fi
}

main() {
    parse_args "$@"

    ensure_repo_root
    load_dotenv
    require_valid_deploy_env
    validate_deploy_contract
    enable_environment_defaults

    echo "========================================"
    echo "Hospital DWH Catalogue Deployment"
    echo "========================================"
    echo ""

    print_deploy_summary

    echo "Rendering compose configuration..."
    run_compose config >/dev/null

    echo "Building and starting services..."
    run_compose up -d --build --remove-orphans

    echo ""
    echo "Running containers:"
    run_compose ps
}

main "$@"
