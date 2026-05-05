# Developer Guide

Audience: developers changing Catalogue behavior or data sources.

Use this page when you are making code changes. For runtime setup, use [OPERATIONS.md](OPERATIONS.md). For integration behavior, use [FAIR_GENOMES.md](FAIR_GENOMES.md).

This guide covers the most common ways developers change the Catalogue.

## Common change paths

- add catalogue filters
- add fields to datasets or distributions
- add another source database or source app
- add pages or endpoints
- change FAIR Genomes statistics
- change ticketing behavior
- add environment variables
- add translations or tests

## Developer workflow

Native Python installs need the LDAP build headers required by `python-ldap`. On Debian,
Ubuntu, or WSL, install them before installing Python requirements:

```bash
sudo apt-get install python3-dev libldap2-dev libsasl2-dev
```

When Docker is available, the check runner can use the containerized toolchain instead
of host LDAP build dependencies.

Install development dependencies with:

```bash
pip install -r requirements-dev.txt
```

Typical workflow:

1. create a branch
2. make your changes
3. run the checks
4. commit and push
5. open a pull request

Run the full local quality suite with:

```bash
./scripts/check.sh
```

The Docker build check is skipped locally when Docker Compose is not usable.

Useful individual commands:

```bash
./scripts/check-lint.sh
./scripts/check-format.sh
./scripts/check-types.sh
./scripts/check-security.sh
./scripts/check-translations.sh
./scripts/check-tests.sh
./scripts/check-docker.sh
```

Optional pre-commit hooks:

```bash
pre-commit install
```

The repo uses:

- `catalogue.settings.dev` for local development
- `catalogue.settings.ci` for tests and automated checks
- `catalogue.settings.staging` for staging
- `catalogue.settings.prod` for production

## Frontend conventions

The frontend is server-rendered Django templates plus lightweight JS libraries vendored under `frontend/static/js/`:

- HTMX for server-driven filtering, pagination, cart toggles, and partial updates
- Alpine.js for local UI state
- Chart.js for FAIR Genomes charts

Rules of thumb:

- use Alpine for UI state that does not need a server round-trip
- use HTMX for interactions that do
- return HTML partials, not JSON, from HTMX view paths
- avoid adding standalone vanilla JS unless the behavior has clearly outgrown inline Alpine logic

## Mental model

Most changes touch one of these layers:

1. source adapters, source models, and database access
2. shared DTOs and mappers
3. unified service orchestration
4. frontend presentation models, filters, and templates
5. export layer

When you make a change, try to keep it inside the narrowest layer possible.

## Add another filter

Most dataset metadata filters are configured in Django admin.

Typical workflow for an already mapped dataset metadata field:

1. open `/admin/`
2. go to Catalogue Frontend > Catalogue filter definitions
3. choose the field name
4. set the sidebar label, order, and enabled flag
5. reload the catalogue

The field-name dropdown only shows mapped metadata fields that do not already
have a filter definition. To change a label, order, or enabled flag for an
existing filter, edit the existing definition instead of adding another one.

The catalogue sidebar and dataset-card preview both use the enabled filter
definitions. If no preview metadata is available for a dataset, the result card
does not open.

Code changes are needed only when the metadata field is not yet mapped into the
unified catalogue model. In that case:

1. add/map the field through the source model, shared DTO, mapper, and frontend view model
2. make sure the field matches a HealthDCAT-AP schema local name, or add an explicit extractor in [frontend/presentation/filter_fields.py](../frontend/presentation/filter_fields.py)
3. add or update frontend tests

The warehouse distribution-column filter is intentionally separate because it
uses table/column lookup logic from `WarehouseMetadataService`.

## Add a new field to existing datasets or distributions

If the source database already contains a new field and you want it in the UI or export:

1. add the field to the concrete model in `warehouse/models.py` or `fair_genomes/models.py`
2. add it to the shared DTO in `shared/dtos.py` if the frontend or export layer should see it
3. map it in `shared/mappers.py`
4. if the frontend should display it, map it in `frontend/presentation/mapping.py`
5. if it should be part of generated DCAT rows, make sure the DTO field name matches the snake_case version of the schema term's `local_name`
6. update templates and tests

For example, if you add a dataset-level field:

- model field
- `UnifiedDataset`
- `map_unified_dataset()`
- maybe `ExportDataset`
- maybe `map_export_dataset()`
- maybe template rendering

## Add another source database with models

This is the biggest extension, but the structure is already there.

### 1. Create a source app

Add a Django app with models similar to `warehouse` or `fair_genomes`.

Decide whether the schema is:

- managed by Django migrations, like `fair_genomes`
- externally managed, like `warehouse`

### 2. Add a database alias

Update:

- [catalogue/settings/helpers.py](../catalogue/settings/helpers.py)
- the relevant environment templates in `env-examples/`
- [scripts/lib/deploy_contract.sh](../scripts/lib/deploy_contract.sh) validation

If the new database should be created automatically in Docker, also update:

- [docker/postgres/initdb.d/00_create_databases.sh](../docker/postgres/initdb.d/00_create_databases.sh)

### 3. Update the database router

Add the new app label to [catalogue/routers.py](../catalogue/routers.py) so reads, writes, relations, and migrations land in the correct DB alias.

### 4. Register the source adapter

Update [shared/source_loaders.py](../shared/source_loaders.py):

- add a `models_loader`
- add a `SourceAdapter`
- choose the `db_alias`
- set `has_table_columns=True` if the source exposes table/column metadata like `warehouse`

### 5. Update mappers and DTOs

Make sure the new source models can be mapped into the shared DTOs in:

- [shared/dtos.py](../shared/dtos.py)
- [shared/mappers.py](../shared/mappers.py)

### 6. Update service logic if needed

If the new source supports:

- table/column drill-down, add a source-specific service and expose it through `UnifiedCatalogService`
- charts/statistics, keep the query in the owning source app and expose it through `UnifiedCatalogService`
- exports, make sure related models and prefetching are supported

### 7. Add tests

At minimum:

- router tests
- source loader tests
- mapping tests
- any new service logic tests

## Add a new page or endpoint

Typical pattern:

1. add a view in `frontend/views.py` or another app
2. register the route in that app's `urls.py`
3. include the route from `catalogue/urls.py` if needed
4. add template(s)
5. add tests

For a new authenticated export/API endpoint, copy the style of `frontend/api_views.py`.

## Change exports

The public export entrypoints live in [shared/export.py](../shared/export.py).

Keep implementation details in focused helper modules:

- `shared/export_specs.py` for DTO-field-to-RDF-property declarations
- `shared/export_values.py` for JSON-LD value coercion
- `shared/export_graph.py` for graph collection, de-duplication, and context trimming
- `shared/export_nodes.py` for catalog, dataset, distribution, agent, contact-point, table, and column nodes

Export functions return result objects with `document` or `content` plus non-fatal warnings.
Surface those warnings through `frontend/export_warnings.py` instead of changing export bodies.

## Add or change FAIR Genomes statistics

If you want another chart:

1. create or edit a `StatDefinition` in the admin
2. save it; for active definitions, the admin immediately tries to synchronise that one aggregation from MOLGENIS
3. if the save-time synchronisation fails or the values need refreshing later, use the selected-stat admin action or `Check and Synchronise FAIR Genomes`
4. verify that the result appears in `StatResult`
5. open the distribution detail page

If a new FAIR Genomes distribution exists in the RDF source but is not yet available in the dropdown, run `Check and Synchronise FAIR Genomes` first. The admin form checks the RDF source inventory through a short-lived cache, but it still saves only locally synchronised `Distribution` rows.

If you need product-level code changes:

- model definitions are in `fair_genomes/models.py`
- admin form construction is in `fair_genomes/services/admin_forms.py`
- admin freshness/source checks are in `fair_genomes/services/admin_support.py`
- stat sync logic is in `fair_genomes/services/stats.py`
- operational freshness state is in `fair_genomes/services/sync_state.py`
- stat loading for distribution pages is in `warehouse/services.py`
- chart normalization is in `frontend/presentation/mapping.py`
- chart rendering templates live under `frontend/templates/catalogue/components/`

## Change FAIR Genomes synchronisation

The main orchestration is in [fair_genomes/services/fair_genomes_service.py](../fair_genomes/services/fair_genomes_service.py).

Current behavior:

- one scheduled/admin run performs an RDF metadata phase and a statistics phase
- `FairGenomesSyncState` stores freshness state for `rdf_metadata` and `statistics` separately
- RDF metadata is fetched, parsed, and persisted from the configured `FAIR_GENOMES_RDF_URL`
- statistics are refreshed from active `StatDefinition` rows through MOLGENIS GraphQL
- the stat-definition admin checks RDF source inventory through a five-minute cache and falls back to locally synchronised distributions

When changing this area, keep RDF metadata freshness and statistic freshness separate. Grouped counts can change even when descriptive RDF metadata does not.

## Add or change ticketing behavior

Important files:

- `ticketing/views.py` — cart and submission flow
- `ticketing/services/factory.py` — mock vs real selection
- `ticketing/services/alvao_service.py` — real Alvao integration

Typical changes:

- change request form fields in `TicketSubmitForm`
- change payload-building logic in the ticket service layer
- add mock behavior first, then the real integration

## Internationalization

The Catalogue supports Czech and English.

When you add or change translatable strings:

```bash
./scripts/compose.sh exec web python manage.py makemessages --all
./scripts/compose.sh exec web python manage.py compilemessages
```

Then update and commit:

- `locale/cs/LC_MESSAGES/django.po`
- `locale/en/LC_MESSAGES/django.po`
- the compiled `.mo` files

In templates:

- use `{% trans %}` for simple strings
- use `{% blocktrans %}` for strings with variables
- use `json_script` when passing translated strings into JavaScript

`docker/startup.py` recompiles translations automatically when needed, but you should still compile and commit them locally so checks pass.

## Add or change HealthDCAT-AP schema behavior

The schema metadata shown in the UI comes from:

- `HEALTH_DCAT_VERSION`
- `schema_registry/services.py`
- `schema_registry/registry.py`

If you update the release:

1. make sure the release exists under `health_dcat_ap/public/releases/`
2. update `HEALTH_DCAT_VERSION`
3. verify term labels, prefixes, and exports
4. update tests if new release semantics changed required fields

## Add a new environment variable

Keep env changes disciplined:

1. decide which environment(s) actually need it
2. add it only to the relevant file(s) in `env-examples/`
3. load it in `catalogue/settings/*` or another real consumer
4. update `scripts/lib/deploy_contract.sh` validation if it is required
5. document it in README or the relevant focused doc

Avoid adding env variables that are not read by code.

## Add translations
Use the internationalization workflow above.

## When to add tests

As a rule:

- new routing logic -> route/view tests
- new filters -> frontend presentation tests
- new source integration -> router + loader + mapping tests
- new auth/admin behavior -> catalogue tests
- new ticketing behavior -> ticketing tests

The project already has good examples in:

- `catalogue/tests.py`
- `frontend/tests.py`
- `ticketing/tests.py`
- `schema_registry/tests.py`

## Related guides

- [OPERATIONS.md](OPERATIONS.md)
- [FAIR_GENOMES.md](FAIR_GENOMES.md)
