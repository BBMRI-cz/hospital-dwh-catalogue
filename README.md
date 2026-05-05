# Hospital Data Warehouse Catalogue

A Django application that publishes hospital data metadata in a HealthDCAT-AP-compatible catalogue, combines multiple metadata sources, and supports access-request workflows through a built-in ticketing flow.

The Catalogue is built for use at [Masaryk Memorial Cancer Institute (MMCI)](https://www.mou.cz/).

## Quick start

Create a local environment:

```bash
./init-env.sh dev
```

Start the stack:

```bash
./deploy.sh
```

Open `http://localhost` and sign in with any non-empty username and password.

## What the Catalogue does

- shows datasets and distributions from the warehouse and FAIR Genomes sources
- lets users search and filter the catalogue
- shows dataset and distribution detail pages
- exposes authenticated aggregate metadata exports at `/api/jsonld` and `/api/rdf`
- lets users add datasets to a cart and submit access requests
- provides an admin panel for staff and a Grafana view for staff users

## Choose the Right Guide

| If you want to... | Read |
|---|---|
| understand the system and its data flow | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| use the running Catalogue as an end user or staff member | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| run, deploy, or operate the stack | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| change the code or extend the product | [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) |

## Subsystem Guide

- [docs/FAIR_GENOMES.md](docs/FAIR_GENOMES.md) — FAIR Genomes sync, statistics, scheduler, and troubleshooting

## Project structure

```text
catalogue/          Settings, middleware, URLs, auth gate, database routers
frontend/           Pages, API views, presentation mapping, templates, static assets
warehouse/          Read-only warehouse metadata models and queries
fair_genomes/       FAIR Genomes models, sync logic, statistics, admin
ticketing/          Cart, ticket submission flow, Alvao integration
shared/             DTOs, mappers, export builders, normalization, source loaders
schema_registry/    HealthDCAT-AP term metadata for the configured HealthDCAT-AP release
docker/             Compose files, nginx config, Dockerfiles, Postgres init
env-examples/       Canonical example environment files
scripts/            Compose wrapper, checks, helper scripts
docs/               Main and focused documentation
```

## Key runtime facts

- server-rendered Django application
- HTMX for partial updates
- Alpine.js for small UI state
- PostgreSQL multi-database setup
- mockable LDAP, FAIR Genomes, and Alvao integrations
- Grafana exposed through Django staff auth

## Most common commands

```bash
./init-env.sh dev
./deploy.sh
./scripts/compose.sh ps
./scripts/compose.sh logs web
./scripts/check.sh
```
