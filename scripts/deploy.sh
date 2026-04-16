#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

WITH_OBSERVABILITY=false

while [ $# -gt 0 ]; do
    case "$1" in
        --with-observability)
            WITH_OBSERVABILITY=true
            shift
            ;;
        --help|-h)
            cat <<'EOF'
Usage: ./scripts/deploy.sh [--with-observability]

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

require_release_dir() {
    local release_dir="health_dcat_ap/public/releases/${HEALTH_DCAT_VERSION}"
    if [ ! -d "$release_dir" ]; then
        echo "Validation error: HEALTH_DCAT_VERSION points to missing release directory: $release_dir" >&2
        return 1
    fi
}

validate_common_contract() {
    require_non_empty \
        DEPLOY_ENV \
        SECRET_KEY \
        DEBUG \
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
        FAIR_GENOMES_SYNC_INTERVAL_HOURS \
        MOCK_LDAP \
        MOCK_FAIR_GENOMES \
        MOCK_ALVAO

    validate_boolean_literal DEBUG
    validate_boolean_literal MOCK_LDAP
    validate_boolean_literal MOCK_FAIR_GENOMES
    validate_boolean_literal MOCK_ALVAO
    require_release_dir
}

validate_staging_contract() {
    require_non_empty GUNICORN_WORKERS

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
    local key

    require_non_empty \
        GUNICORN_WORKERS \
        SERVER_NAME \
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

    for key in MOCK_LDAP MOCK_FAIR_GENOMES MOCK_ALVAO; do
        if [ "${!key}" != "False" ]; then
            echo "Validation error: $key must be False in production." >&2
            return 1
        fi
    done

    if [ "${DEBUG}" != "False" ]; then
        echo "Validation error: DEBUG must be False in production." >&2
        return 1
    fi

    validate_boolean_literal EMAIL_USE_TLS
    validate_boolean_literal SECURE_SSL_REDIRECT
}

run_compose_wrapper() {
    if [ "$WITH_OBSERVABILITY" = true ]; then
        "$SCRIPT_DIR/compose.sh" --with-observability "$@"
    else
        "$SCRIPT_DIR/compose.sh" "$@"
    fi
}

echo "========================================"
echo "Hospital DWH Catalogue Deployment"
echo "========================================"
echo ""

validate_common_contract

case "$DEPLOY_ENV" in
    dev)
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
