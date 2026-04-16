# Deployment

## Prerequisites

- Docker and Docker Compose installed
- A `.env` file created from one of:
  - `.env.dev.example`
  - `.env.staging.example`
  - `.env.prod.example`
- `DEPLOY_ENV` in `.env` set to `dev`, `staging`, or `prod`

## Canonical commands

Use the provided scripts instead of calling compose files directly:

```bash
./scripts/deploy.sh
./scripts/compose.sh ps
```

`./scripts/deploy.sh` is the canonical deployment entrypoint. It:

1. Loads `.env`
2. Validates the environment contract for the selected `DEPLOY_ENV`
3. Verifies the configured `HEALTH_DCAT_VERSION` release directory exists
4. Renders the matching compose stack
5. Starts or updates the containers with `up -d --build --remove-orphans`

For dev or staging, include observability explicitly:

```bash
./scripts/deploy.sh --with-observability
```

Production always includes Loki, Promtail, and Grafana.

## Compose layout

The Docker Compose config is split into focused layers under `docker/compose/`:

- `base.yml` -- shared app services (`db`, `web`, `scheduler`, `nginx`)
- `dev.yml` -- bind mounts, `runserver`, no Redis
- `staging.yml` -- Gunicorn, Redis, named volumes, HTTP-only proxy
- `prod.yml` -- production runtime, TLS, Certbot, stricter restart/network settings
- `check.yml` -- optional `check` service used by quality scripts
- `observability.yml` -- Loki, Promtail, Grafana

Use `./scripts/compose.sh` for manual operations because it assembles the right file set for the current `.env` automatically.

Examples:

```bash
./scripts/compose.sh up -d --build
./scripts/compose.sh exec web python manage.py createsuperuser
./scripts/compose.sh logs scheduler
./scripts/compose.sh --with-observability ps
```

## Validation rules

The deploy script validates more than just `DEPLOY_ENV`:

- All environments must define the core Django settings, all four PostgreSQL database aliases, bootstrap superuser credentials, mock flags, and `HEALTH_DCAT_VERSION`.
- Staging requires `GUNICORN_WORKERS` and conditionally requires LDAP, FAIR Genomes, or Alvao credentials when the matching `MOCK_*` flag is `False`.
- Production requires live LDAP, FAIR Genomes, Alvao, email, proxy, and TLS settings; `DEBUG` must be `False`, and all `MOCK_*` flags must be `False`.

This validation mirrors the actual runtime expectations more closely than the old docs-only guidance.

## What happens on container startup

The web container entrypoint (`docker/entrypoint.sh` calling `docker/startup.py`) runs these steps automatically:

1. Creates the logs directory
2. Migrates `auth_db`
3. Creates or updates the env-managed superuser from `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD`
4. Migrates the default database
5. Repairs ticketing migration drift if the migration state says a table exists but the table is missing
6. Migrates `fair_genomes_db`
7. Repairs FAIR Genomes migration drift if core tables are missing
8. Migrates `metadata_db` when it is reachable
9. Seeds mock FAIR Genomes data when `MOCK_FAIR_GENOMES=True`
10. Builds Tailwind CSS
11. Compiles translations when `.po` files are newer than `.mo`
12. Runs `collectstatic` outside development

You do not need to run migrations or collectstatic manually during normal deployment.

## Environment differences

| | Dev | Staging | Prod |
|---|---|---|---|
| App server | Django `runserver` | Gunicorn | Gunicorn |
| Bind mounts | Yes | No | No |
| Redis | No | Yes | Yes |
| TLS / Certbot | No | No | Yes |
| Observability | Opt-in | Opt-in | Always on |
| Mock integrations | Default on | Individually configurable | Forbidden |

Staging is intentionally much closer to production than development is.

## Manual maintenance

Create an extra superuser:

```bash
./scripts/compose.sh exec web python manage.py createsuperuser
```

Collect static files manually:

```bash
./scripts/compose.sh exec web python manage.py collectstatic --noinput
```

Render the effective stack without starting it:

```bash
./scripts/compose.sh config
```

Render the effective stack with observability:

```bash
./scripts/compose.sh --with-observability config
```
