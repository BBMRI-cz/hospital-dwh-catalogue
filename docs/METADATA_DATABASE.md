# Metadata Database

The Django app owns warehouse catalogue content through the `metadata_db`
database alias. Django migrations create and evolve the `metadata.lm_*` tables.

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

## Managed Metadata DB

All environment examples use a separate catalogue-owned metadata database:

```env
METADATA_DB_NAME=warehouse_metadata_dev
METADATA_DB_HOST=db
```

The Postgres init script creates `METADATA_DB_NAME` when it points at the
stack-local `db` service. The web startup then runs Django migrations against
`metadata_db`.

Postgres init scripts only run when the Docker volume is first created. Existing
dev/staging volumes need either a reset or a manual database creation before the
web container can migrate `metadata_db`.

## Mock Metadata

Development enables:

```env
MOCK_WAREHOUSE_METADATA=True
```

After `metadata_db` migrations finish, startup runs:

```bash
python manage.py seed_warehouse_mock
```

The seeder writes public sample rows into the catalogue-owned `metadata.lm_*`
tables. Staging and production keep `MOCK_WAREHOUSE_METADATA=False` by default.

## Updating Metadata From SQL

The warehouse team can update the catalogue metadata database with SQL through
the repository helper script:

```bash
./scripts/run-metadata-sql.sh /path/to/warehouse_metadata_load.sql
```

The script loads `.env`, uses `METADATA_DB_NAME`, `METADATA_DB_USER`, and
`METADATA_DB_PASSWORD`, and runs `psql` inside the Compose `db` service. It does
not require a second database user or a network-exposed Postgres port.

Multiple files can be supplied and are executed in order:

```bash
./scripts/run-metadata-sql.sh 01_contacts.sql 02_datasets.sql 03_tables.sql
```

Each file is executed in one transaction by default. Use `--no-transaction` only
for SQL that cannot run inside a transaction:

```bash
./scripts/run-metadata-sql.sh --no-transaction /path/to/script.sql
```

Write only to the managed `metadata.lm_*` tables. Do not change Django migration
state, drop the schema, or alter ownership from loader SQL.

Use upserts so repeated loads are safe:

```sql
INSERT INTO metadata."lm_contact_point" (id, email, contact_page)
OVERRIDING SYSTEM VALUE
VALUES (100, 'metadata@example.org', NULL)
ON CONFLICT (id) DO UPDATE
SET email = EXCLUDED.email,
    contact_page = EXCLUDED.contact_page;

INSERT INTO metadata."lm_agent" (name, contact_point_id, description)
VALUES ('AGENT_DWH', 100, 'Warehouse metadata owner')
ON CONFLICT (name) DO UPDATE
SET contact_point_id = EXCLUDED.contact_point_id,
    description = EXCLUDED.description;
```

## Legacy Imports

`00_ddl_dwhi_test_metadata.sql` originally created only these legacy tables:

- `metadata.datasource_list`
- `metadata.dataset_list`
- `metadata.dataclass_list`
- `metadata.dataclass_table_schemes`
- `metadata.db_table_list`
- `metadata.db_table_schemes`

The current catalogue stores migrated metadata in:

- `metadata.lm_contact_point`
- `metadata.lm_agent`
- `metadata.lm_catalog`
- `metadata.lm_dataset`
- `metadata.lm_distribution`
- `metadata.lm_table`
- `metadata.lm_column`

Do not commit site-specific legacy dumps or private migration scripts to this
repository. Keep those files outside git and run them manually with the
metadata SQL runner after Django has created the managed tables.
