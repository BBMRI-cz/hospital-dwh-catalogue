# Operations

Audience: operators and developers running the stack.

Use this page to bootstrap `.env`, deploy or update the containers, understand startup behavior, and handle routine maintenance.

## Fast paths

### Local development

```bash
./init-env.sh dev
./deploy.sh
```

### Staging or production

```bash
./init-env.sh staging
./init-env.sh prod
```

Then fill the generated `.env` with real values and run:

```bash
./deploy.sh
```

Use `./deploy.sh --with-observability` in dev or staging when you want Loki, Promtail, and Grafana too. Production always includes the observability stack.

## Environment model

| Environment | Main purpose | Auth mode | FAIR Genomes / Alvao | Runtime shape |
|---|---|---|---|---|
| `dev` | local development | mocked LDAP | mocked by default | `runserver`, bind mounts, no Redis |
| `staging` | pre-production validation | LDAP mocked by default | live-like by default | Gunicorn, Redis, named volumes, internal HTTPS |
| `prod` | live deployment | real LDAP only | real integrations only | Gunicorn, internal HTTPS, observability always on |

## Environment bootstrap

Create `.env` with:

```bash
./init-env.sh dev
./init-env.sh staging
./init-env.sh prod
```

What it does:

- copies the matching file from `env-examples/`
- keeps the fixed placeholder key in `dev`
- generates a fresh `SECRET_KEY` for `staging` and `prod`

Use `--force` if you intentionally want to overwrite an existing `.env`.

## Environment values by subsystem

### Core app and databases

All environments need the core Django settings, bootstrap superuser credentials, and all four PostgreSQL aliases:

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `SITE_URL`
- `HEALTH_DCAT_VERSION`
- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_PASSWORD`
- `POSTGRES_*`
- `AUTH_DB_*`
- `METADATA_DB_*`
- `FAIR_GENOMES_DB_*`

### Authentication

The app supports:

- mock LDAP for local and isolated testing
- real LDAP for live authentication

Environment defaults:

- `dev` uses mock LDAP
- `staging` usually uses mock LDAP, but can switch to real LDAP
- `prod` uses real LDAP only

Relevant variables:

- `MOCK_LDAP`
- `AUTH_LDAP_SERVER_URI`
- `AUTH_LDAP_BIND_DN`
- `AUTH_LDAP_BIND_PASSWORD`
- `AUTH_LDAP_USER_SEARCH_BASE`
- `AUTH_LDAP_LOGIN_ATTR` defaults to `sAMAccountName` and can be changed to `userPrincipalName` if your directory uses that login format
- `AUTH_LDAP_START_TLS` when your directory uses StartTLS instead of `ldaps://`
- `AUTH_LDAP_CA_CERT_PATH` in production when the LDAP server certificate chains to an internal CA

When `MOCK_LDAP=True`:

- any non-empty username and password are accepted
- the username matching `DJANGO_SUPERUSER_USERNAME` becomes staff and superuser
- other users are created as regular Django users on first login

When `MOCK_LDAP=False`, the app authenticates against Active Directory through a service account search + bind flow. Successful LDAP users get a local Django account on first login, but staff and superuser rights remain managed locally in Django.

### FAIR Genomes

Relevant variables:

- `MOCK_FAIR_GENOMES`
- `FAIR_GENOMES_RDF_URL`
- `FAIR_GENOMES_API_URL`
- `FAIR_GENOMES_API_TOKEN`
- `FAIR_GENOMES_SYNC_INTERVAL_HOURS`

`dev` usually keeps FAIR Genomes mocked. `staging` and `prod` normally point to real FAIR Genomes services.

### Ticketing / Alvao

Relevant variables:

- `MOCK_ALVAO`
- `ALVAO_API_URL`
- `ALVAO_SERVICE_ACCOUNT_USERNAME`
- `ALVAO_SERVICE_ACCOUNT_PASSWORD`
- `ALVAO_DEFAULT_SERVICE_ID`

When `MOCK_ALVAO=True`, the app stores local mock ticket requests and does not call an external system. When `MOCK_ALVAO=False`, it uses one service account with HTTP Basic Auth to create Alvao tickets on behalf of users.

### HTTPS certificates for staging and production

By default, both deployed environments expect these repository-root relative paths in `.env`:

- `certs/server.crt`
- `certs/server.key`

If the files live elsewhere, set these optional repo-root relative overrides in `.env`:

- `NGINX_SSL_CERT_PATH`
- `NGINX_SSL_KEY_PATH`

The nginx container mounts those repo-root relative files directly for TLS termination. The
internal `MOURootCA` stays a client trust concern on managed PCs; the application does not
need a separate runtime CA file for this setup.

### Deployed HTTPS settings

Staging and production both need:

- `SERVER_NAME`
- `GUNICORN_WORKERS`

Production also needs:

- `ADMIN_EMAIL`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `SECURE_SSL_REDIRECT`
- `SECURE_HSTS_SECONDS`

## Deploying or updating the stack

The canonical deploy command is:

```bash
./deploy.sh
```

For dev or staging with observability:

```bash
./deploy.sh --with-observability
```

`deploy.sh`:

1. loads `.env`
2. validates the contract for the selected `DEPLOY_ENV`
3. attempts to update `health_dcat_ap` from Git when Git metadata is available
4. checks the configured `HEALTH_DCAT_VERSION`
5. renders the compose stack
6. starts or updates the services

Before deploying `staging` or `prod`, place the provided certificate and private key into the
repo-root `certs/` directory as `server.crt` and `server.key`. The generated `.env` already
uses the repo-root relative values `certs/server.crt` and `certs/server.key`; change those
only when the files live somewhere else inside or relative to the repository checkout.

## Validation contract

The deploy script validates the environment before it starts anything.

Shared requirements for all environments:

- core Django settings such as `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL`, and `HEALTH_DCAT_VERSION`
- bootstrap superuser credentials
- all four PostgreSQL database aliases
- `FAIR_GENOMES_SYNC_INTERVAL_HOURS`

Environment-specific requirements:

- `dev` also requires the three `MOCK_*` flags
- `staging` also requires `DEBUG`, `GUNICORN_WORKERS`, `SERVER_NAME`, valid TLS certificate files, and real credentials only for integrations whose `MOCK_*` flag is `False`
- `prod` requires `GUNICORN_WORKERS`, `SERVER_NAME`, `ADMIN_EMAIL`, valid TLS certificate files, live LDAP / FAIR Genomes / Alvao credentials, and email settings
- production LDAP also requires `AUTH_LDAP_LOGIN_ATTR`, `AUTH_LDAP_START_TLS`, and `AUTH_LDAP_CA_CERT_PATH`

This keeps the docs and the real runtime contract aligned.

## Compose layout

The stack is built from:

- `docker/compose/base.yml`
- `docker/compose/dev.yml`
- `docker/compose/staging.yml`
- `docker/compose/prod.yml`
- `docker/compose/check.yml`
- `docker/compose/observability.yml`

Use [scripts/compose.sh](../scripts/compose.sh) for all manual compose operations. It chooses the right file combination from `.env`.

## Startup behavior

The web container runs [docker/startup.py](../docker/startup.py) before starting the server.

It:

1. migrates `auth_db`
2. creates or updates the env-managed superuser
3. migrates `default`
4. repairs ticketing migration drift if needed
5. migrates `fair_genomes_db`
6. repairs FAIR Genomes migration drift if needed
7. attempts `metadata_db` migration
8. seeds mock FAIR Genomes data when enabled
9. builds Tailwind CSS
10. compiles translations when needed
11. runs `collectstatic` outside development

You normally do not need to run migrations or `collectstatic` by hand during normal deployment.

## Database behavior

The Postgres container creates:

- `POSTGRES_DB` automatically
- `AUTH_DB_NAME` if needed
- `FAIR_GENOMES_DB_NAME` if needed

This behavior lives in [docker/postgres/initdb.d/00_create_databases.sh](../docker/postgres/initdb.d/00_create_databases.sh).

`metadata_db` usually points to the same underlying database as `POSTGRES_DB`, but through a dedicated alias in Django.

## Auth and admin operations

The env-managed superuser is controlled by:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_PASSWORD`

That account is re-applied on every startup.

Good practice:

- use a username that does not exist in LDAP
- treat it as a bootstrap or break-glass admin account
- grant real staff access through the Django admin

## Admin access and roles

Roles in practice:

- authenticated user — can browse the catalogue and submit requests
- staff user — can open `/admin/` and `/grafana/`
- superuser — has full Django admin access

To avoid collisions with real directory users, `DJANGO_SUPERUSER_USERNAME` should be a service-style username that does not exist in Active Directory.

Good examples:

```text
app-admin
_dwh-admin
```

Bad examples:

```text
john.smith
admin
```

If you need another superuser outside the env-managed bootstrap account:

```bash
./scripts/compose.sh exec web python manage.py createsuperuser
```

If a manually created user shares the same username as `DJANGO_SUPERUSER_USERNAME`, the startup logic may reclaim it on the next restart if it looks like a local-password superuser.

## What can be managed in admin

From `/admin/` you can:

- manage users and permissions
- manage FAIR Genomes stat definitions
- trigger FAIR Genomes sync actions
- inspect ticket requests

Warehouse metadata is not managed in Django admin. It is read directly from `metadata_db`.

## User creation and permissions

On first successful login, Django creates the user automatically in `auth_db`.

New users have no special permissions by default. Grant access through the Django admin by setting:

- `is_staff` for admin and Grafana access
- `is_superuser` for full administrative control
- group memberships for any future role-based permissions

## Observability

The observability stack includes:

- Loki
- Promtail
- Grafana

Grafana is available at `/grafana/`, but only for logged-in Django staff users. There is no separate Grafana password.

## Maintenance commands

Rebuild containers:

```bash
./scripts/compose.sh up -d --build
```

Restart one service:

```bash
./scripts/compose.sh restart web
```

Open container logs:

```bash
./scripts/compose.sh logs web
./scripts/compose.sh logs scheduler
./scripts/compose.sh logs nginx
```

Open a shell inside the web container:

```bash
./scripts/compose.sh exec web bash
```

Render the effective stack without starting it:

```bash
./scripts/compose.sh config
./scripts/compose.sh --with-observability config
```

## Quality and CI

Run all checks:

```bash
./scripts/check.sh
```

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

## Troubleshooting

### Local login does not work

Check:

- `.env` was created with `./init-env.sh dev`
- `MOCK_LDAP=True`
- the `web` container is running

### `deploy.sh` fails before containers start

Check:

- the missing variable reported by the validation step
- `DEPLOY_ENV` matches the template you used
- `HEALTH_DCAT_VERSION` points to an existing release directory
- the TLS certificate and key exist either in `certs/` at the repo root or at the override paths from `.env`

### Users cannot log in with real LDAP

Check:

- `MOCK_LDAP=False`
- `AUTH_LDAP_SERVER_URI`, `AUTH_LDAP_BIND_DN`, `AUTH_LDAP_BIND_PASSWORD`, `AUTH_LDAP_USER_SEARCH_BASE`, and `AUTH_LDAP_LOGIN_ATTR` are set
- `AUTH_LDAP_CA_CERT_PATH` points to the internal LDAP CA certificate when your directory uses internal PKI
- the LDAP server is reachable from the containers
- the user can actually bind through LDAP with the supplied credentials

### Warehouse data is missing

Check:

- `metadata_db` credentials are correct
- the warehouse schema exists
- startup logs do not say `metadata_db migration skipped`

### FAIR Genomes data or charts are missing

Check:

- `MOCK_FAIR_GENOMES` matches the environment you want
- the scheduler or manual sync has run
- `FAIR_GENOMES_RDF_URL`, `FAIR_GENOMES_API_URL`, and `FAIR_GENOMES_API_TOKEN` are set when mocks are off

### Ticket requests are not reaching Alvao

Check:

- `MOCK_ALVAO` matches the environment you want
- `ALVAO_API_URL`, `ALVAO_SERVICE_ACCOUNT_USERNAME`, `ALVAO_SERVICE_ACCOUNT_PASSWORD`, and `ALVAO_DEFAULT_SERVICE_ID` are set when mocks are off
- web container logs for outbound request or retry errors

### Grafana is accessible or blocked unexpectedly

Check:

- the user is authenticated in Django
- the user has `is_staff=True`
- requests are going through nginx instead of bypassing it

## Release data

The schema and export semantics depend on `HEALTH_DCAT_VERSION`, which points to a checked-out release under:

`health_dcat_ap/public/releases/<version>`

If you change the release:

1. make sure `health_dcat_ap` contains that release, either in the checked-out copy or via Git update during deploy
2. update `.env`
3. rerun deploy
4. verify schema labels and exports

## Useful references

- [FAIR_GENOMES.md](FAIR_GENOMES.md) — FAIR Genomes sync and stats
- [USER_GUIDE.md](USER_GUIDE.md) — user-facing app behavior
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — code changes and development workflow
