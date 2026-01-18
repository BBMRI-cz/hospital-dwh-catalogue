#!/bin/sh

set -e

pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v /docker-entrypoint-initdb.d/initial_data.backup
