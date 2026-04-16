# Hospital Data Warehouse Catalogue

A HealthDCAT-AP v6 compliant data catalogue for hospital data warehouse metadata. The application is built with Django, PostgreSQL, and Docker Compose.

## Quick start

1. Copy the development environment template:

   ```bash
   cp .env.dev.example .env
   ```

2. Start the stack:

   ```bash
   ./scripts/deploy.sh
   ```

   For direct Docker Compose access, use the env-aware wrapper:

   ```bash
   ./scripts/compose.sh up -d --build
   ```

3. Open http://localhost in a browser.

4. Log in with any username and password. This only works in development with `MOCK_LDAP=True`.

## Documentation

- [Admin Guide](docs/ADMIN.md) -- managing users, content, and the admin panel
- [Authentication](docs/AUTHENTICATION.md) -- mock auth in dev/staging and LDAP in production
- [Deployment](docs/DEPLOYMENT.md) -- env files, compose layout, and deployment workflow
- [Contributing](docs/CONTRIBUTING.md) -- development workflow and code quality checks
- [Internationalization](docs/INTERNATIONALIZATION.md) -- adding and updating translations
- [FAIR Genomes](docs/FAIR_GENOMES.md) -- MOLGENIS integration, data sync, and scheduling
- [Stats Setup](docs/STATS.md) -- configuring statistics and charts for FAIR Genomes distributions
- [Ticketing](docs/TICKETING.md) -- Alvao Service Desk integration

## Project structure

```text
catalogue/          Django project settings, middleware, URL config, DB routers
frontend/           Catalogue frontend (views, routes, templates, static assets)
warehouse/          Warehouse metadata source app
fair_genomes/       FAIR Genomes integration, sync, stats, admin
ticketing/          Ticket request system and Alvao integration
shared/             Shared services, DTOs, assemblers, export helpers
schema_registry/    HealthDCAT-AP SHACL schema loader
health_dcat_ap/     Git submodule with HealthDCAT-AP release files
docker/             Dockerfiles, compose overrides, nginx, Postgres, logging config
locale/             Translation files (Czech and English)
scripts/            Deployment, compose wrapper, and quality-check scripts
docs/               Project documentation
```

## Frontend

The UI is server-rendered Django templates styled with Tailwind CSS. Interactive behavior is handled without a Node.js build pipeline:

- HTMX 2 for server-driven filtering, pagination, and cart actions
- Alpine.js 3 for dropdowns, accordions, modals, toasts, and inline UI state
- Chart.js for FAIR Genomes stat charts

## Metadata export API

The catalogue exposes one aggregate HealthDCAT-AP export covering all source catalogs, datasets, and distributions from the warehouse and FAIR Genomes metadata databases.

- JSON-LD: `/api/jsonld`
- RDF Turtle: `/api/rdf`

## Databases

Runtime environments use four PostgreSQL database aliases:

| Alias | Example default name | Contents |
|---|---|---|
| `default` | `dwhi_dev` | Ticketing models and any non-routed Django app tables |
| `auth_db` | `hospital_dwh_auth` | Users, groups, permissions, sessions, admin logs |
| `metadata_db` | `dwhi_dev` | Warehouse catalogue tables (managed externally, read-only to the app) |
| `fair_genomes_db` | `fair_genomes` | FAIR Genomes datasets, distributions, stat definitions, stat results |

CI uses the separate `catalogue.settings.ci` module with SQLite databases for fast automated checks.

## Environment files

Use one of the canonical example files and copy it to `.env`:

- `.env.dev.example` -- local development with mock integrations
- `.env.staging.example` -- pre-production deployment, mockable per integration
- `.env.prod.example` -- live deployment with real integrations

All three example files share the same variable order and sections. `DEPLOY_ENV` in `.env` selects the stack shape.

## Docker Compose layout

The deployment surface is split into a small shared base plus focused overrides:

- `docker/compose/base.yml` -- shared app services
- `docker/compose/dev.yml` -- bind mounts, runserver, lean local stack
- `docker/compose/staging.yml` -- Gunicorn, Redis, named volumes
- `docker/compose/prod.yml` -- TLS, Certbot, stricter production runtime
- `docker/compose/check.yml` -- check runner used by quality scripts
- `docker/compose/observability.yml` -- Loki, Promtail, Grafana

Use:

- `./scripts/deploy.sh` for full stack deployment
- `./scripts/compose.sh` for manual stack operations

## Services

| Service | Purpose |
|---|---|
| `db` | PostgreSQL 17 database server |
| `web` | Django app (`runserver` in dev, Gunicorn in staging/prod) |
| `scheduler` | Cron-based FAIR Genomes sync worker |
| `nginx` | Reverse proxy and static file server |
| `redis` | Cache and session backend in staging/prod |
| `check` | Optional containerized QA runner |
| `loki` / `promtail` / `grafana` | Optional observability stack outside prod, always included in prod |
