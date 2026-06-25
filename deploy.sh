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
DEFAULT_HEALTH_TIMEOUT_SECONDS=180

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

sync_repository_for_deploy() {
    local before_pull
    local after_pull

    if [ "$DEPLOY_ENV" = "dev" ] || [ "${DEPLOY_GIT_PULL_REEXECED:-}" = "true" ]; then
        return
    fi

    if ! command -v git >/dev/null 2>&1; then
        echo "git is required to deploy $DEPLOY_ENV because deploy pulls the latest code." >&2
        return 1
    fi

    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "Cannot deploy $DEPLOY_ENV from a directory that is not a Git checkout." >&2
        return 1
    fi

    before_pull="$(git rev-parse HEAD)"
    echo "Updating repository for $DEPLOY_ENV with git pull --ff-only..."
    git pull --ff-only
    after_pull="$(git rev-parse HEAD)"

    if [ "$before_pull" != "$after_pull" ]; then
        echo "Repository updated; restarting deploy script with the pulled code..."
        DEPLOY_GIT_PULL_REEXECED=true exec "$0" "$@"
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
    local timeout_seconds="${DEPLOY_HEALTH_TIMEOUT_SECONDS:-$DEFAULT_HEALTH_TIMEOUT_SECONDS}"

    for attempt in $(seq 1 "$timeout_seconds"); do
        if run_compose exec -T db pg_isready \
            --username "$POSTGRES_USER" \
            --dbname postgres >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "Timed out waiting ${timeout_seconds}s for the Postgres container to become ready." >&2
    return 1
}

service_health() {
    local service="$1"
    local status_json

    status_json="$(run_compose ps --format json "$service" 2>/dev/null || true)"

    case "$status_json" in
        *'"Health":"healthy"'*)
            echo "healthy"
            ;;
        *'"Health":"unhealthy"'*)
            echo "unhealthy"
            ;;
        *'"State":"exited"'*|*'"State":"dead"'*)
            echo "stopped"
            ;;
        *)
            echo "starting"
            ;;
    esac
}

wait_for_web() {
    local attempt
    local health
    local timeout_seconds="${DEPLOY_HEALTH_TIMEOUT_SECONDS:-$DEFAULT_HEALTH_TIMEOUT_SECONDS}"

    for attempt in $(seq 1 "$timeout_seconds"); do
        health="$(service_health web)"

        if [ "$health" = "healthy" ]; then
            return 0
        fi

        if [ "$health" = "unhealthy" ] || [ "$health" = "stopped" ]; then
            echo "Web container reached health state '$health' before becoming healthy." >&2
            run_compose ps web >&2 || true
            return 1
        fi

        sleep 1
    done

    echo "Timed out waiting ${timeout_seconds}s for the web container to become healthy." >&2
    run_compose ps web >&2 || true
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

alvao_is_mocked() {
    if [ "$DEPLOY_ENV" = "prod" ]; then
        return 1
    fi

    [ "${MOCK_ALVAO:-True}" = "True" ]
}

should_check_alvao() {
    ! alvao_is_mocked
}

ldap_is_mocked() {
    if [ "$DEPLOY_ENV" = "prod" ]; then
        return 1
    fi

    [ "${MOCK_LDAP:-True}" = "True" ]
}

should_check_ldap() {
    ! ldap_is_mocked
}

run_post_deploy_diagnostics() {
    echo "Waiting for web health check..."
    wait_for_web

    if should_check_ldap; then
        echo "Checking LDAP TLS/bind/search reachability..."
        if ! run_compose exec -T web python manage.py check_ldap_connection; then
            echo "WARNING: LDAP post-deploy check failed." >&2
        fi
    fi

    if should_check_alvao; then
        echo "Checking ALVAO TLS/API reachability..."
        if ! run_compose exec -T web python manage.py check_alvao_tls; then
            echo "WARNING: ALVAO post-deploy check failed." >&2
        fi
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

    echo "DB viewer access: ${POSTGRES_PUBLISH_HOST:-127.0.0.1}:${POSTGRES_PUBLISH_PORT:-15432} on the server; use an SSH tunnel from the workstation"
}

main() {
    parse_args "$@"

    ensure_repo_root
    load_dotenv
    require_valid_deploy_env
    sync_repository_for_deploy "$@"
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

    run_post_deploy_diagnostics

    echo ""
    echo "Running containers:"
    run_compose ps
}

main "$@"
