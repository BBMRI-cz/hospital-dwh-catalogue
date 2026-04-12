# Hospital Data Warehouse Catalogue

A HealthDCAT-AP v6 compliant data catalogue for hospital data warehouse metadata. Built with Django, PostgreSQL, and Docker.

## Quick start

1. Copy the example environment file:

   ```bash
   cp .env.dev.example .env
   ```

2. Start the application:

   ```bash
   sh ./deploy.sh
   ```

   Or run it manually:

   ```bash
   docker compose -f docker-compose.dev.yml up -d --build
   ```

3. Open http://localhost in a browser.

4. Log in with any username and password. The first login creates a superuser. Subsequent logins create regular users. This only works in dev mode with `MOCK_LDAP=True`.

## Documentation

- [Admin Guide](docs/ADMIN.md) -- managing users, content, and the admin panel
- [Authentication](docs/AUTHENTICATION.md) -- dev auth backend and production LDAP setup
- [Deployment](docs/DEPLOYMENT.md) -- deploying to dev, test, and production
- [Contributing](docs/CONTRIBUTING.md) -- development workflow and code quality checks
- [Internationalization](docs/INTERNATIONALIZATION.md) -- adding and updating translations
- [FAIR Genomes](docs/FAIR_GENOMES.md) -- MOLGENIS integration, data sync, and scheduling
- [Stats Setup](docs/STATS.md) -- configuring statistics and charts for FAIR Genomes distributions
- [Ticketing](docs/TICKETING.md) -- Alvao Service Desk integration

## Project structure

```
catalogue/          Django project settings, middleware, URL config, DB routers
frontend/           Catalogue frontend (views, routes, templates, static assets, page/API presentation layer)
warehouse/          Warehouse metadata source app (models, source-specific services)
fair_genomes/       FAIR Genomes integration (models, sync service, admin, stats)
ticketing/          Ticket request system (cart, Alvao API client)
shared/             Abstract models, DTOs, mappers, unified catalog service
schema_registry/    HealthDCAT-AP SHACL schema loader (from git submodule)
health_dcat_ap/     Git submodule with HealthDCAT-AP release files
docker/             Dockerfile, entrypoint scripts, Nginx, Postgres, Grafana configs
locale/             Translation files (Czech and English)
scripts/            Code quality and CI check scripts
docs/               Project documentation
```

## Frontend

The UI is server-rendered Django templates styled with Tailwind CSS. Interactive behaviour is handled by two vendored libraries (no build step, no npm):

- **HTMX 2** (`frontend/static/js/htmx.min.js`) — server-driven updates: catalogue filtering, pagination, cart toggles with out-of-band badge swaps.
- **Alpine.js 3** (`frontend/static/js/alpine.min.js`) — client-side state: dropdowns, accordions, inline search, toasts, modals.
- **Chart.js** (`frontend/static/js/chart.umd.min.js`) — FAIR Genomes stat doughnut charts.

## Metadata export API

The catalogue exposes one aggregate HealthDCAT-AP export covering all source
catalogs, datasets, and distributions from the warehouse and FAIR Genomes
metadata databases.

- JSON-LD: `/api/jsonld`
- RDF Turtle: `/api/rdf`

## Databases

The application uses four databases:

| Alias | Default name | Contents |
|---|---|---|
| `auth_db` | `hospital_dwh_auth` | Users, groups, permissions, sessions, admin logs |
| `metadata_db` | `hospital_dwh` | Warehouse catalogue tables (managed externally, read-only) |
| `fair_genomes_db` | `fair_genomes` | FAIR Genomes datasets, distributions, stat definitions, stat results |
| `default` | SQLite (dev) | Ticketing models |

## Environment variables

Each environment has its own example file:

- `.env.dev.example` -- local development with mock services
- `.env.test.example` -- test server deployment
- `.env.prod.example` -- production deployment

Copy the appropriate file to `.env` and fill in the values. See the example files for the full list of variables. Key settings:

| Variable | Purpose |
|---|---|
| `DEPLOY_ENV` | `dev`, `test`, or `prod` -- selects docker-compose file |
| `SECRET_KEY` | Django secret key (generate a strong random string for prod) |
| `MOCK_LDAP` | `True` to use the dev auth backend, `False` for LDAP |
| `MOCK_FAIR_GENOMES` | `True` to seed sample data instead of syncing from MOLGENIS |
| `MOCK_ALVAO` | `True` to use the mock ticketing service |
| `DJANGO_SUPERUSER_USERNAME` | Bootstrap superuser username (created on startup) |
| `DJANGO_SUPERUSER_PASSWORD` | Bootstrap superuser password |
| `FAIR_GENOMES_RDF_URL` | FAIR Data Point RDF endpoint for metadata sync |
| `FAIR_GENOMES_API_URL` | MOLGENIS GraphQL endpoint for stats and data sync |
| `FAIR_GENOMES_API_TOKEN` | Authentication token for the MOLGENIS API |
| `FAIR_GENOMES_SYNC_INTERVAL_HOURS` | How often the scheduler syncs data (default: 24) |
| `MOCK_FAIR_GENOMES` | Set to `True` to use seeded mock data instead of a live MOLGENIS instance |
| `SITE_URL` | Public base URL for JSON-LD export (e.g. `https://your-domain.com`) |
| `HEALTH_DCAT_VERSION` | HealthDCAT-AP release to use (default: `release-6`) |

## Docker services

| Service | Purpose |
|---|---|
| `db` | PostgreSQL 17 database server |
| `web` | Django application (runserver in dev, Gunicorn in test/prod) |
| `scheduler` | Cron-based FAIR Genomes sync service |
| `nginx` | Reverse proxy, serves static files |
| `redis` | Cache and sessions (test/prod only) |
| `loki` | Log aggregation |
| `promtail` | Log collector |
| `grafana` | Monitoring dashboards |
