# Architecture

Audience: developers, operators, and anyone who wants a mental model of the system.

Use this page to understand how the app is organized before you deploy it, debug it, or extend it.

## What this app is

The Hospital DWH Catalogue is a Django application that publishes metadata about hospital data sources in a HealthDCAT-AP-compatible catalogue.

It combines metadata from multiple source applications:

- `warehouse` — the main hospital data warehouse catalogue stored in `metadata_db`
- `fair_genomes` — FAIR Genomes datasets and statistics stored in `fair_genomes_db`
- `ticketing` — local ticket requests stored in `default`
- Django auth/admin/session data in `auth_db`

The app is server-rendered. Users log in, browse datasets and distributions, filter the catalogue, inspect details, export metadata, and request access through the ticketing flow.

## Main user flows

- Browse the catalogue at `/`
- Open a dataset detail page at `/dataset/<app>/<name>/`
- Open a distribution detail page at `/distribution/<app>/<name>/`
- Download authenticated aggregate exports from `/api/jsonld` and `/api/rdf`
- Add datasets to the cart at `/cart/` and view request history at `/tickets/`
- Open `/admin/` for content and user administration
- Open `/grafana/` as a logged-in staff user for observability

## How the app is structured

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
2. `shared/source_loaders.py` loads source data from the right database alias
3. `shared/mappers.py` converts models into shared DTOs from `shared/dtos.py`
4. `shared/services.py` provides a single `UnifiedCatalogService`
5. `frontend/presentation/*` turns DTOs into view models, filtering, sidebars, and cache snapshots
6. `shared/export.py` builds aggregate HealthDCAT-AP JSON-LD and Turtle exports

This separation is what makes the app easy to extend:

- source-specific schema details stay in the source app
- the frontend reads normalized DTOs
- exports do not need to know which database produced a record

## Database layout

The runtime uses four aliases:

| Alias | Purpose |
|---|---|
| `default` | Ticketing tables and uncategorized Django app tables |
| `auth_db` | Users, groups, permissions, sessions, admin logs |
| `metadata_db` | Warehouse catalogue tables, managed outside Django |
| `fair_genomes_db` | FAIR Genomes models and statistics |

The routing rules live in [catalogue/routers.py](../catalogue/routers.py).

## Environment model

The project has three runtime environments:

- `dev` — smallest config surface, all integrations mocked
- `staging` — LDAP mocked by default, FAIR Genomes and Alvao configured like a live environment
- `prod` — real integrations only

Environment templates live in [env-examples/](../env-examples/), and `.env` is created with `./init-env.sh`.

## Frontend model

The frontend is intentionally simple:

- Django templates render the pages
- HTMX handles server-driven updates like filtering and pagination
- Alpine.js handles small pieces of UI state
- Chart.js renders FAIR Genomes stat charts

There is no Node.js build pipeline for the UI.

## Exports

The app exposes two authenticated aggregate export endpoints:

- `/api/jsonld`
- `/api/rdf`

Dataset detail pages also expose per-dataset exports for logged-in users.

The schema terms shown in the UI come from the configured HealthDCAT-AP release via `schema_registry`.

## Integrations

- Authentication: mock LDAP in dev/staging or real LDAP in prod
- FAIR Genomes: RDF metadata + MOLGENIS GraphQL statistics sync
- Ticketing: mock service or real Alvao REST API
- Observability: Loki, Promtail, Grafana behind Django staff auth

## Read this next

- [USER_GUIDE.md](USER_GUIDE.md) — how to use the app
- [OPERATIONS.md](OPERATIONS.md) — deployment and maintenance
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — how to change and extend the app
