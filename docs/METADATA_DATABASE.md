# Metadata Database

The Django app reads warehouse catalogue content from the `metadata_db` database
alias. It expects the `metadata.lm_*` tables defined in
`docker/postgres/initdb.d/01_ddl.sql`.

## Local Network Access

The development compose override publishes Postgres with:

```yaml
${POSTGRES_PUBLISH_HOST:-0.0.0.0}:${POSTGRES_PUBLISH_PORT:-5433}:5432
```

With the default dev example, another machine on the same network can connect to
the Docker host IP on port `5433`.

Use these databases:

- `dwhi_dev` for the catalogue application database.
- `warehouse_metadata_dev` for warehouse metadata.
- `hospital_dwh_auth` for users, groups, and sessions.
- `fair_genomes` for FAIR Genomes state.

If the database should only be reachable from the local computer, set:

```env
POSTGRES_PUBLISH_HOST=127.0.0.1
```

Exposing Postgres on a LAN should be limited to trusted networks and protected
with a non-default password plus host firewall rules.

## Separate Metadata DB

For new dev and staging stacks, the env examples now use a separate metadata
database:

```env
METADATA_DB_NAME=warehouse_metadata_dev
METADATA_DB_HOST=db
```

When `METADATA_DB_HOST` points at the stack-local Postgres service, the init
scripts create `METADATA_DB_NAME` and load the same `metadata.lm_*` schema/mock
data there. If `METADATA_DB_HOST` points at an external warehouse database, the
stack-local init skips that external target.

Postgres init scripts only run when the Docker volume is first created. Existing
dev/staging volumes need either a reset or a manual database/schema load.

## Legacy Schema Migration

`00_ddl_dwhi_test_metadata.sql` originally created only these legacy tables:

- `metadata.datasource_list`
- `metadata.dataset_list`
- `metadata.dataclass_list`
- `metadata.dataclass_table_schemes`
- `metadata.db_table_list`
- `metadata.db_table_schemes`

The current catalogue needs these additional tables:

- `metadata.lm_contact_point`
- `metadata.lm_agent`
- `metadata.lm_catalog`
- `metadata.lm_dataset`
- `metadata.lm_distribution`
- `metadata.lm_table`
- `metadata.lm_column`

For a fresh database, the local `00_ddl_dwhi_test_metadata.sql` has been updated
to create both the legacy tables and the `lm_*` compatibility tables, so the
current `02_mock_data.sql` can load.

For an existing old-format database, run:

```bash
psql "$DATABASE_URL" -f scripts/migrate_legacy_metadata_to_lm.sql
```

The migration script creates missing `lm_*` tables and copies legacy rows into
the new shape. It preserves dataset, dataclass, table, and column names where
possible and fills mandatory HealthDCAT-AP fields with defaults because the old
schema did not contain those values.
