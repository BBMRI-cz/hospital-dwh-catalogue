#!/bin/sh

[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/run-metadata-sql.sh [--no-transaction] <file.sql> [file2.sql ...]

Runs one or more SQL files against the configured warehouse metadata database.
The script loads .env, uses METADATA_DB_NAME, METADATA_DB_USER, and
METADATA_DB_PASSWORD, and executes psql inside the Compose db service.

Options:
  --no-transaction   Do not wrap each file in one psql transaction.
  --help             Show this message.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

PSQL_TRANSACTION_ARGS=(--single-transaction)
SQL_FILES=()

while [ $# -gt 0 ]; do
    case "$1" in
        --no-transaction)
            PSQL_TRANSACTION_ARGS=()
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        --)
            shift
            while [ $# -gt 0 ]; do
                SQL_FILES+=("$1")
                shift
            done
            break
            ;;
        -*)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
        *)
            SQL_FILES+=("$1")
            ;;
    esac
    shift
done

if [ "${#SQL_FILES[@]}" -eq 0 ]; then
    usage >&2
    exit 1
fi

ensure_repo_root
load_dotenv
require_valid_deploy_env
export_mou_root_ca_fingerprint
build_compose_args "$DEPLOY_ENV" false false

for sql_file in "${SQL_FILES[@]}"; do
    if [ ! -f "$sql_file" ]; then
        echo "SQL file does not exist: $sql_file" >&2
        exit 1
    fi

    if [ ! -r "$sql_file" ]; then
        echo "SQL file is not readable: $sql_file" >&2
        exit 1
    fi

    echo "Running metadata SQL: $sql_file"

    docker_compose --env-file "$DOTENV_FILE" "${COMPOSE_ARGS[@]}" exec -T db sh -c '
        set -eu
        : "${METADATA_DB_NAME:?METADATA_DB_NAME is not set}"
        : "${METADATA_DB_USER:?METADATA_DB_USER is not set}"
        : "${METADATA_DB_PASSWORD:?METADATA_DB_PASSWORD is not set}"

        export PGPASSWORD="$METADATA_DB_PASSWORD"
        exec psql \
            --set=ON_ERROR_STOP=1 \
            --host=127.0.0.1 \
            --username="$METADATA_DB_USER" \
            --dbname="$METADATA_DB_NAME" \
            "$@"
    ' sh "${PSQL_TRANSACTION_ARGS[@]}" < "$sql_file"
done
