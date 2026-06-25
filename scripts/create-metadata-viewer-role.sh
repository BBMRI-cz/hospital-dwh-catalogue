#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

usage() {
    cat <<'EOF'
Usage: METADATA_VIEWER_USER=<user> bash ./scripts/create-metadata-viewer-role.sh

Creates or updates a read-only PostgreSQL login for the catalogue-owned
metadata database. The role can SELECT from the metadata schema only.

Optional:
  METADATA_VIEWER_PASSWORD=<password>  Supply the password non-interactively.
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

ensure_repo_root
load_dotenv
require_valid_deploy_env

: "${METADATA_VIEWER_USER:?METADATA_VIEWER_USER is not set}"

if [ -z "${METADATA_VIEWER_PASSWORD:-}" ]; then
    printf "Password for PostgreSQL role '%s': " "$METADATA_VIEWER_USER"
    read -r -s METADATA_VIEWER_PASSWORD
    printf "\n"
fi

if [ -z "$METADATA_VIEWER_PASSWORD" ]; then
    echo "METADATA_VIEWER_PASSWORD cannot be empty." >&2
    exit 1
fi

./scripts/compose.sh exec -T db psql \
    --username "$POSTGRES_USER" \
    --dbname "$METADATA_DB_NAME" \
    --set=ON_ERROR_STOP=1 \
    --set=viewer_user="$METADATA_VIEWER_USER" \
    --set=viewer_password="$METADATA_VIEWER_PASSWORD" <<'EOSQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'viewer_user', :'viewer_password')
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_roles
    WHERE rolname = :'viewer_user'
)\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'viewer_user', :'viewer_password')\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'viewer_user')\gexec
SELECT format('GRANT USAGE ON SCHEMA metadata TO %I', :'viewer_user')\gexec
SELECT format('GRANT SELECT ON ALL TABLES IN SCHEMA metadata TO %I', :'viewer_user')\gexec
SELECT format('ALTER DEFAULT PRIVILEGES IN SCHEMA metadata GRANT SELECT ON TABLES TO %I', :'viewer_user')\gexec
EOSQL

echo "Read-only metadata viewer role '$METADATA_VIEWER_USER' is ready."
