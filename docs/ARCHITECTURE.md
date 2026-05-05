# Architecture

Audience: developers, operators, and anyone who wants a mental model of the system.

Use this page to understand how the Catalogue is organized before you deploy it, debug it, or extend it.

## What the Catalogue is

The Hospital Data Warehouse Catalogue is a Django application that publishes metadata about hospital data sources in a HealthDCAT-AP-compatible catalogue.

It combines metadata from multiple source applications:

- `warehouse` — the main hospital data warehouse catalogue loaded through `metadata_db`
- `fair_genomes` — FAIR Genomes datasets and statistics stored in `fair_genomes_db`
- `ticketing` — local ticket requests stored in `default`
- Django auth/admin/session data in `auth_db`

The Catalogue is server-rendered. Users log in, browse datasets and distributions, filter the catalogue, inspect details, export metadata, and request access through the ticketing flow.

## Main user flows

- Browse the catalogue at `/`
- Open a dataset detail page at `/dataset/<app>/<name>/`
- Open a distribution detail page at `/distribution/<app>/<name>/`
- Download authenticated aggregate exports from `/api/jsonld` and `/api/rdf`
- Add datasets to the cart at `/cart/` and view request history at `/tickets/`
- Open `/admin/` for content and user administration
- Open `/grafana/` as a logged-in staff user for observability

## How the Catalogue is structured

### Django apps

- `catalogue` — settings, URL configuration, middleware, database routers
- `frontend` — catalogue pages, API views, presentation mapping, templates, static assets
- `warehouse` — read-only metadata models for the hospital warehouse schema
- `fair_genomes` — managed models, sync logic, statistics, admin actions
- `ticketing` — cart, request submission, Alvao integration
- `schema_registry` — HealthDCAT-AP term metadata loader for the configured release
- `shared` — DTOs, mappers, export builders, normalization, catalogue assembly

### Data flow

The important architectural pattern is:

1. Source-specific Django models live in `warehouse` and `fair_genomes`
2. `shared/source_loaders.py` registers source adapters that know their database alias and query shape
3. `shared/mappers.py` converts models into shared DTOs from `shared/dtos.py`
4. `shared/services.py` provides a single `UnifiedCatalogService` orchestration facade
5. `frontend/presentation/*` turns DTOs into view models, filtering, sidebars, and cache snapshots
6. `shared/export.py` exposes the export facade, while focused export helper modules build HealthDCAT-AP JSON-LD and Turtle payloads

This separation is what makes the Catalogue easy to extend:

- source-specific schema details stay in the source app
- the frontend reads normalized DTOs
- exports do not need to know which database produced a record
- adding a source means adding a source adapter instead of changing frontend or export code

## Database layout

The runtime uses four aliases:

| Alias | Purpose |
|---|---|
| `default` | Ticketing tables and uncategorized Django app tables |
| `auth_db` | Users, groups, permissions, sessions, admin logs |
| `metadata_db` | Warehouse catalogue tables in an externally managed schema; in production this usually points to a warehouse-owned database outside the app stack |
| `fair_genomes_db` | FAIR Genomes models and statistics |

The routing rules live in [catalogue/routers.py](../catalogue/routers.py).

## Environment model

The project has three runtime environments:

- `dev` — smallest config surface, all integrations mocked
- `staging` — LDAP mocked by default, FAIR Genomes and Alvao configured like a live environment
- `prod` — real integrations only, with `metadata_db` connected to the external warehouse database

In production, `metadata_db` sits outside the deployed app stack. Development and staging can still point that alias at a stack-local Postgres clone when needed.

Environment templates live in [env-examples/](../env-examples/), and `.env` is created with `./init-env.sh`.

## Frontend model

The frontend is intentionally simple:

- Django templates render the pages
- HTMX handles server-driven updates like filtering and pagination
- Alpine.js handles small pieces of UI state
- Chart.js renders FAIR Genomes stat charts

There is no Node.js build pipeline for the UI.

## Exports

The Catalogue exposes two authenticated aggregate export endpoints:

- `/api/jsonld`
- `/api/rdf`

Dataset detail pages also expose per-dataset exports for logged-in users.

Export builders use the configured schema registry context profile. Missing RDF classes,
properties, or terms are non-fatal and are returned as export warnings on the page and in
download/API response headers.

The schema terms shown in the UI come from the configured HealthDCAT-AP release via `schema_registry`.

## Integrations

- Authentication: mock LDAP in dev/staging or real LDAP in prod
- FAIR Genomes: RDF metadata + MOLGENIS GraphQL statistics sync
- Ticketing: mock service or real Alvao REST API
- Observability: Loki, Promtail, Grafana behind Django staff auth

## Read this next

- [USER_GUIDE.md](USER_GUIDE.md) — how to use the Catalogue
- [OPERATIONS.md](OPERATIONS.md) — deployment and maintenance
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — how to change and extend the Catalogue
