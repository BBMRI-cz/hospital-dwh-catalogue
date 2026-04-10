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

# The Postgres image creates POSTGRES_DB automatically. The metadata schema bootstraps
# into that database, so only the extra logical databases need to be created here.
create_database "${AUTH_DB_NAME:-}"
create_database "${FAIR_GENOMES_DB_NAME:-}"