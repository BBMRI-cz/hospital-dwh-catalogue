#!/bin/sh
set -eu

metadata_host="${METADATA_DB_HOST:-db}"

if [ "$metadata_host" != "db" ] && [ "$metadata_host" != "localhost" ] && [ "$metadata_host" != "127.0.0.1" ]; then
    echo "Skipping stack-local metadata database init because METADATA_DB_HOST=$metadata_host"
elif [ -z "${METADATA_DB_NAME:-}" ] || [ "$METADATA_DB_NAME" = "$POSTGRES_DB" ]; then
    :
else
    echo "Initializing stack-local metadata database '$METADATA_DB_NAME'..."
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$METADATA_DB_NAME" \
        --file /docker-entrypoint-initdb.d/01_ddl.sql
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$METADATA_DB_NAME" \
        --file /docker-entrypoint-initdb.d/02_mock_data.sql
fi
