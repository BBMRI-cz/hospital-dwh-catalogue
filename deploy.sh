#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/scripts/lib/common.sh"
# shellcheck source=scripts/lib/deploy_contract.sh
source "$SCRIPT_DIR/scripts/lib/deploy_contract.sh"

WITH_OBSERVABILITY=false
RESET_VOLUMES=false
RESET_KEEP_USERS=false
ASSUME_YES=false
AUTH_DB_BACKUP_FILE=""

usage() {
    cat <<'EOF'
Usage: ./deploy.sh [--with-observability] [--reset-volumes | --reset-volumes-keep-users] [--yes]

Reads DEPLOY_ENV from .env, validates the environment contract,
and starts the matching Docker Compose stack.

Use --with-observability to include Loki, Grafana Alloy, and Grafana for dev.
Staging and production always include the observability stack.

Reset options:
  --reset-volumes             Stop the stack and delete all Docker Compose volumes before deploy.
  --reset-volumes-keep-users  Delete volumes but preserve auth_db users, groups, and permissions.
  --yes                       Skip the confirmation prompt for reset options.
EOF
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --with-observability)
                WITH_OBSERVABILITY=true
                ;;
            --reset-volumes)
                RESET_VOLUMES=true
                ;;
            --reset-volumes-keep-users)
                RESET_VOLUMES=true
                RESET_KEEP_USERS=true
                ;;
            --yes|-y)
                ASSUME_YES=true
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
    if [ "$DEPLOY_ENV" = "prod" ] || [ "$DEPLOY_ENV" = "staging" ]; then
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

confirm_reset() {
    local expected="reset-$DEPLOY_ENV"
    local response

    if [ "$RESET_VOLUMES" != true ] || [ "$ASSUME_YES" = true ]; then
        return
    fi

    echo ""
    echo "WARNING: this will stop the $DEPLOY_ENV stack and delete all Compose volumes."
    echo "This includes Postgres, static files, logs, Loki, Alloy, and Grafana data."

    if [ "$RESET_KEEP_USERS" = true ]; then
        echo "The auth database will be exported first and restored after the reset."
    fi

    printf "Type '%s' to continue: " "$expected"
    read -r response

    if [ "$response" != "$expected" ]; then
        echo "Reset aborted."
        exit 1
    fi
}

wait_for_db() {
    local attempt

    for attempt in $(seq 1 60); do
        if run_compose exec -T db pg_isready \
            --username "$POSTGRES_USER" \
            --dbname postgres >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "Timed out waiting for the Postgres container to become ready." >&2
    return 1
}

backup_auth_db() {
    AUTH_DB_BACKUP_FILE="$(mktemp "${TMPDIR:-/tmp}/hospital-dwh-auth-db.XXXXXX.dump")"

    echo "Starting database service for auth_db export..."
    run_compose up -d db
    wait_for_db

    echo "Exporting auth database '$AUTH_DB_NAME' to $AUTH_DB_BACKUP_FILE..."
    if ! run_compose exec -T db pg_dump \
        --username "$POSTGRES_USER" \
        --dbname "$AUTH_DB_NAME" \
        --format=custom \
        --no-owner \
        --no-privileges > "$AUTH_DB_BACKUP_FILE"; then
        echo "Failed to export auth database. The reset was not started." >&2
        echo "Partial backup file, if any: $AUTH_DB_BACKUP_FILE" >&2
        return 1
    fi
}

restore_auth_db() {
    echo "Starting clean database service for auth_db restore..."
    run_compose up -d db
    wait_for_db

    echo "Restoring auth database '$AUTH_DB_NAME'..."
    run_compose exec -T db pg_restore \
        --username "$POSTGRES_USER" \
        --dbname "$AUTH_DB_NAME" \
        --format=custom \
        --single-transaction \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges < "$AUTH_DB_BACKUP_FILE"

    echo "Clearing restored sessions and admin log entries..."
    run_compose exec -T db psql \
        --username "$POSTGRES_USER" \
        --dbname "$AUTH_DB_NAME" \
        --set=ON_ERROR_STOP=1 <<'EOSQL'
TRUNCATE TABLE django_session, django_admin_log RESTART IDENTITY;
EOSQL

    rm -f "$AUTH_DB_BACKUP_FILE"
    AUTH_DB_BACKUP_FILE=""
}

reset_persistent_state() {
    if [ "$RESET_VOLUMES" != true ]; then
        return
    fi

    confirm_reset

    if [ "$RESET_KEEP_USERS" = true ]; then
        backup_auth_db
    fi

    echo "Stopping stack and deleting Docker Compose volumes..."
    run_compose down --volumes --remove-orphans

    if [ "$RESET_KEEP_USERS" = true ]; then
        restore_auth_db
    fi
}

print_deploy_summary() {
    echo "Target environment: $DEPLOY_ENV"

    if [ "$DEPLOY_ENV" = "prod" ] || [ "$DEPLOY_ENV" = "staging" ]; then
        echo "Observability: always-on in $DEPLOY_ENV"
    elif [ "$WITH_OBSERVABILITY" = true ]; then
        echo "Observability: enabled"
    else
        echo "Observability: disabled"
    fi

    if [ "$RESET_KEEP_USERS" = true ]; then
        echo "Reset: delete all volumes, then restore auth_db users/groups/permissions"
    elif [ "$RESET_VOLUMES" = true ]; then
        echo "Reset: delete all volumes"
    else
        echo "Reset: disabled"
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
    echo "Hospital Data Warehouse Catalogue Deployment"
    echo "========================================"
    echo ""

    print_deploy_summary

    echo "Rendering compose configuration..."
    run_compose config >/dev/null

    reset_persistent_state

    echo "Building and starting services..."
    run_compose up -d --build --remove-orphans

    echo ""
    echo "Running containers:"
    run_compose ps
}

main "$@"
