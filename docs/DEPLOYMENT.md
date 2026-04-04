# Deployment

## Prerequisites

- Docker and Docker Compose installed
- A `.env` file created from the appropriate example (`.env.dev.example`, `.env.test.example`, or `.env.prod.example`)
- The `DEPLOY_ENV` variable in `.env` set to `dev`, `test`, or `prod`

## Using the deploy script

The simplest way to deploy:

```bash
./deploy.sh
```

What the script does:

1. Reads `DEPLOY_ENV` from `.env` to pick the right docker-compose file
2. Pulls the latest code from git (skipped for `dev`)
3. Updates the HealthDCAT-AP git submodule
4. Stops existing containers
5. Builds and starts new containers

## Manual deployment

If you prefer to run the steps yourself:

```bash
docker compose -f docker-compose.<env>.yml build
docker compose -f docker-compose.<env>.yml up -d
```

Replace `<env>` with `dev`, `test`, or `prod`.

## What happens on container startup

The web container entrypoint (`docker/entrypoint.sh` calling `docker/startup.py`) runs these steps automatically:

1. Creates the logs directory
2. Migrates the `auth_db` database
3. Creates or updates the env-managed superuser from `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` (see [Admin Guide](ADMIN.md)). Skipped if either variable is not set.
4. Migrates the `default` database
5. Migrates the `fair_genomes_db` database (includes automatic drift repair if core tables are missing)
6. Migrates the `metadata_db` database
7. Seeds mock data if `MOCK_FAIR_GENOMES=True`
8. Compiles translation messages if `.po` files are newer than `.mo` files
9. Runs `collectstatic` (test and prod only)

You do not need to run migrations or collectstatic manually.

## Environment differences

| | Dev | Test | Prod |
|---|---|---|---|
| Web server | Django runserver | Gunicorn (2 workers) | Gunicorn (configurable) |
| Redis | No | Yes | Yes |
| SSL | No | No | Yes (Certbot) |
| Mock services | All mocked | All mocked | All real |
| Git pull on deploy | No | Yes | Yes |

## Production-specific setup

For production, make sure you have set:

- `SECRET_KEY` -- a strong random string
- `ALLOWED_HOSTS` -- your production domain
- `SECURE_SSL_REDIRECT=True` -- forces HTTPS
- `SERVER_NAME` -- your domain (used by Nginx and Certbot)
- `AUTH_LDAP_*` -- LDAP connection details (see [Authentication](AUTHENTICATION.md))
- `FAIR_GENOMES_*` -- MOLGENIS API details (see [FAIR Genomes](FAIR_GENOMES.md))
- `ALVAO_*` -- Alvao API details (see [Ticketing](TICKETING.md))
- `EMAIL_*` -- SMTP settings for error notifications

See `.env.prod.example` for the full list.

## Collecting static files

In development, Django serves static files directly. In test and production, `collectstatic` runs automatically on container startup. If you need to run it manually:

```bash
docker compose -f docker-compose.<env>.yml exec web python manage.py collectstatic --noinput
```

## Monitoring

Grafana is available at `/grafana/` (requires staff status). Loki collects logs from all containers via Promtail.
