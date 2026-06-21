#!/bin/sh
set -eu

create_database() {
    db_name="$1"

    if [ -z "$db_name" ] || [ "$db_name" = "$POSTGRES_DB" ]; then
        return
    fi

    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres --set=db_name="$db_name" <<'EOSQL'
SELECT format('CREATE DATABASE %I', :'db_name')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name')\gexec
EOSQL
}

# The Postgres image creates POSTGRES_DB automatically. Extra logical databases
# are created here when they are backed by the stack-local Postgres service.
create_database "${AUTH_DB_NAME:-}"
if [ "${METADATA_DB_HOST:-db}" = "db" ] || [ "${METADATA_DB_HOST:-db}" = "localhost" ] || [ "${METADATA_DB_HOST:-db}" = "127.0.0.1" ]; then
    create_database "${METADATA_DB_NAME:-}"
fi
create_database "${FAIR_GENOMES_DB_NAME:-}"
