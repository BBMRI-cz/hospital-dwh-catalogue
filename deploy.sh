#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/scripts/lib/common.sh"

WITH_OBSERVABILITY=false

while [ $# -gt 0 ]; do
    case "$1" in
        --with-observability)
            WITH_OBSERVABILITY=true
            shift
            ;;
        --help|-h)
            cat <<'EOF'
Usage: ./deploy.sh [--with-observability]

Reads DEPLOY_ENV from .env, validates the environment contract,
and starts the matching Docker Compose stack.

Use --with-observability to include Loki, Promtail, and Grafana for
dev or staging. Production always includes the observability stack.
EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

ensure_repo_root
load_dotenv
require_valid_deploy_env

validate_boolean_literal() {
    local key="$1"
    local value="${!key:-}"

    case "$value" in
        True|False)
            return 0
            ;;
        *)
            echo "Validation error: $key must be set to True or False in .env." >&2
            return 1
            ;;
    esac
}

require_non_empty() {
    local key
    for key in "$@"; do
        if [ -z "${!key:-}" ]; then
            echo "Validation error: $key must be set in .env." >&2
            return 1
        fi
    done
}

resolve_path_from_repo_root() {
    local path="$1"

    case "$path" in
        *)
            printf '%s\n' "$REPO_ROOT/$path"
            ;;
    esac
}

require_relative_path() {
    local key="$1"
    local value="${!key:-}"

    case "$value" in
        /*)
            echo "Validation error: $key must be a repo-root relative path in .env." >&2
            return 1
            ;;
    esac
}

require_existing_file() {
    local key="$1"
    local configured_path="${!key:-}"
    local effective_path

    if [ -z "$configured_path" ]; then
        echo "Validation error: $key must be set in .env." >&2
        return 1
    fi

    effective_path="$(resolve_path_from_repo_root "$configured_path")"

    if [ ! -f "$effective_path" ]; then
        echo "Validation error: $key points to a missing file: $effective_path" >&2
        return 1
    fi
}

maybe_update_health_dcat_release() {
    local submodule_path="health_dcat_ap"
    local releases_root="${submodule_path}/public/releases"

    if ! command -v git >/dev/null 2>&1; then
        return 0
    fi

    if ! git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return 0
    fi

    if [ ! -f "$REPO_ROOT/.gitmodules" ] || ! grep -Fq "path = $submodule_path" "$REPO_ROOT/.gitmodules"; then
        return 0
    fi

    echo "Updating HealthDCAT release files..."
    if ! git -C "$REPO_ROOT" submodule update --init --recursive --remote -- "$submodule_path"; then
        echo "Warning: failed to update $submodule_path from remote; continuing with the local checkout." >&2
    fi
}

require_release_dir() {
    local submodule_path="health_dcat_ap"
    local releases_root="${submodule_path}/public/releases"
    local release_dir="${releases_root}/${HEALTH_DCAT_VERSION}"
    local escaped_version
    printf -v escaped_version '%q' "$HEALTH_DCAT_VERSION"

    maybe_update_health_dcat_release

    if [ ! -d "$releases_root" ]; then
        echo "Validation error: missing release root: $releases_root" >&2
        echo "Deploy could not update or initialize $submodule_path automatically." >&2
        echo "Make sure the $submodule_path submodule or release files are present on this server." >&2
        return 1
    fi

    if [ ! -d "$release_dir" ]; then
        echo "Validation error: HEALTH_DCAT_VERSION=$escaped_version points to missing release directory: $release_dir" >&2
        echo "Check .env for hidden characters or typos, and make sure the updated $submodule_path checkout contains that release." >&2
        return 1
    fi
}

validate_common_contract() {
    require_non_empty \
        DEPLOY_ENV \
        SECRET_KEY \
        ALLOWED_HOSTS \
        SITE_URL \
        HEALTH_DCAT_VERSION \
        DJANGO_SUPERUSER_USERNAME \
        DJANGO_SUPERUSER_PASSWORD \
        POSTGRES_DB \
        POSTGRES_USER \
        POSTGRES_PASSWORD \
        POSTGRES_HOST \
        POSTGRES_PORT \
        AUTH_DB_NAME \
        AUTH_DB_USER \
        AUTH_DB_PASSWORD \
        AUTH_DB_HOST \
        AUTH_DB_PORT \
        METADATA_DB_NAME \
        METADATA_DB_USER \
        METADATA_DB_PASSWORD \
        METADATA_DB_HOST \
        METADATA_DB_PORT \
        FAIR_GENOMES_DB_NAME \
        FAIR_GENOMES_DB_USER \
        FAIR_GENOMES_DB_PASSWORD \
        FAIR_GENOMES_DB_HOST \
        FAIR_GENOMES_DB_PORT \
        FAIR_GENOMES_SYNC_INTERVAL_HOURS

    require_release_dir
}

validate_mock_contract() {
    require_non_empty \
        MOCK_LDAP \
        MOCK_FAIR_GENOMES \
        MOCK_ALVAO

    validate_boolean_literal MOCK_LDAP
    validate_boolean_literal MOCK_FAIR_GENOMES
    validate_boolean_literal MOCK_ALVAO
}

validate_dev_contract() {
    validate_mock_contract
}

validate_tls_contract() {
    require_non_empty SERVER_NAME NGINX_SSL_CERT_PATH NGINX_SSL_KEY_PATH
    require_relative_path NGINX_SSL_CERT_PATH
    require_relative_path NGINX_SSL_KEY_PATH
    require_existing_file NGINX_SSL_CERT_PATH
    require_existing_file NGINX_SSL_KEY_PATH
}

validate_staging_contract() {
    require_non_empty DEBUG GUNICORN_WORKERS

    validate_boolean_literal DEBUG
    validate_mock_contract
    validate_tls_contract

    if [ "${MOCK_LDAP}" = "False" ]; then
        require_non_empty \
            AUTH_LDAP_SERVER_URI \
            AUTH_LDAP_BIND_DN \
            AUTH_LDAP_BIND_PASSWORD \
            AUTH_LDAP_USER_SEARCH_BASE
    fi

    if [ "${MOCK_FAIR_GENOMES}" = "False" ]; then
        require_non_empty \
            FAIR_GENOMES_RDF_URL \
            FAIR_GENOMES_API_URL \
            FAIR_GENOMES_API_TOKEN
    fi

    if [ "${MOCK_ALVAO}" = "False" ]; then
        require_non_empty \
            ALVAO_API_URL \
            ALVAO_SERVICE_ACCOUNT_USERNAME \
            ALVAO_SERVICE_ACCOUNT_PASSWORD \
            ALVAO_DEFAULT_SERVICE_ID
    fi
}

validate_prod_contract() {
    require_non_empty \
        GUNICORN_WORKERS \
        ADMIN_EMAIL \
        AUTH_LDAP_SERVER_URI \
        AUTH_LDAP_BIND_DN \
        AUTH_LDAP_BIND_PASSWORD \
        AUTH_LDAP_USER_SEARCH_BASE \
        FAIR_GENOMES_RDF_URL \
        FAIR_GENOMES_API_URL \
        FAIR_GENOMES_API_TOKEN \
        ALVAO_API_URL \
        ALVAO_SERVICE_ACCOUNT_USERNAME \
        ALVAO_SERVICE_ACCOUNT_PASSWORD \
        ALVAO_DEFAULT_SERVICE_ID \
        EMAIL_HOST \
        EMAIL_PORT \
        EMAIL_HOST_USER \
        EMAIL_HOST_PASSWORD \
        EMAIL_USE_TLS \
        SECURE_SSL_REDIRECT \
        SECURE_HSTS_SECONDS

    validate_boolean_literal EMAIL_USE_TLS
    validate_boolean_literal SECURE_SSL_REDIRECT
    validate_tls_contract
}

run_compose_wrapper() {
    if [ "$WITH_OBSERVABILITY" = true ]; then
        "$SCRIPT_DIR/scripts/compose.sh" --with-observability "$@"
    else
        "$SCRIPT_DIR/scripts/compose.sh" "$@"
    fi
}

echo "========================================"
echo "Hospital DWH Catalogue Deployment"
echo "========================================"
echo ""

validate_common_contract

case "$DEPLOY_ENV" in
    dev)
        validate_dev_contract
        echo "Target environment: dev"
        ;;
    staging)
        validate_staging_contract
        echo "Target environment: staging"
        ;;
    prod)
        validate_prod_contract
        echo "Target environment: prod"
        WITH_OBSERVABILITY=true
        ;;
esac

if [ "$WITH_OBSERVABILITY" = true ] && [ "$DEPLOY_ENV" != "prod" ]; then
    echo "Observability: enabled"
else
    echo "Observability: $([ "$DEPLOY_ENV" = "prod" ] && echo "always-on in prod" || echo "disabled")"
fi

echo "Rendering compose configuration..."
run_compose_wrapper config >/dev/null

echo "Building and starting services..."
run_compose_wrapper up -d --build --remove-orphans

echo ""
echo "Running containers:"
run_compose_wrapper ps
