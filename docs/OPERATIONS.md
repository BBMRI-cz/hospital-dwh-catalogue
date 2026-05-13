# Operations

Audience: operators and developers running the stack.

Use this page to bootstrap `.env`, deploy or update the containers, understand startup behavior, and handle routine maintenance.

## Fast paths

### Local development

```bash
./init-env.sh dev
./deploy.sh
```

### Staging

```bash
./init-env.sh staging
```

### Production

```bash
./init-env.sh prod
```

Then fill the generated `.env` with real values for the selected environment and run:

```bash
./deploy.sh
```

Staging and production always include Loki, Grafana Alloy, and Grafana. Use `./deploy.sh --with-observability` only when you also want observability in dev.

The helper scripts require Bash. Run them with `./init-env.sh`, `./deploy.sh`, or `bash <script>`

## Environment bootstrap

Create `.env` with:

```bash
./init-env.sh dev
./init-env.sh staging
./init-env.sh prod
```

Run only the command for the environment you want to create. Each command writes the repository-root `.env` file.

What it does:

- copies the matching file from `env-examples/`
- keeps the fixed placeholder key in `dev`
- generates a fresh `SECRET_KEY` for `staging` and `prod`

Use `--force` if you intentionally want to overwrite an existing `.env`.

## Environment values by subsystem

### Core Catalogue and databases

All environments need the core Django settings, env-managed superuser credentials, and all four PostgreSQL aliases:

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

On startup, the account named by `DJANGO_SUPERUSER_USERNAME` is created or updated as
staff and superuser in every environment, including `staging` and `prod`, as long
as the username does not already belong to an LDAP-only user. `DJANGO_SUPERUSER_PASSWORD`
is the local password for that env-managed account.

Optional Catalogue tuning:

- `CATALOGUE_PAGE_SIZE` controls how many datasets the main catalogue page shows per page and defaults to `15`

In production, `METADATA_DB_*` should point to the external warehouse-owned database, not to the stack-local `db` container.

### Authentication

The Catalogue supports:

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
- `MOU_ROOT_CA_CERT_PATH` for the shared MOU root CA certificate

When `MOCK_LDAP=True`:

- any non-empty username and password are accepted
- other users are created as regular Django users on first login

When `MOCK_LDAP=False`, the Catalogue authenticates against Active Directory through a service account search + bind flow. Successful LDAP users get a local Django account on first login, but staff and superuser rights remain managed locally in Django. The env-managed superuser is still applied during startup independently of LDAP mode.

Real LDAP deployments use the shared MOU root CA from `MOU_ROOT_CA_CERT_PATH`. The web container installs it into the system trust store and points OpenLDAP at the resulting system CA bundle.

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

When `MOCK_ALVAO=True`, the Catalogue stores local mock ticket requests and does not call an external system. When `MOCK_ALVAO=False`, it uses one service account with HTTP Basic Auth to create Alvao tickets on behalf of users.

Set `ALVAO_API_URL` to the versioned REST API base URL, for example `https://alvao.example.cz/AlvaoRestApi/v1`.

For real Alvao integration, the MOU root CA certificate configured by `MOU_ROOT_CA_CERT_PATH` must be present. Staging and production mount this file into the Python containers and use it for outbound HTTPS verification.

### HTTPS certificates for staging and production

By default, both deployed environments expect these repository-root relative paths in `.env`:

- `certs/server.crt`
- `certs/server.key`
- `certs/MOURootCA.crt`

If the files live elsewhere, set these optional repo-root relative overrides in `.env`:

- `NGINX_SSL_CERT_PATH`
- `NGINX_SSL_KEY_PATH`
- `MOU_ROOT_CA_CERT_PATH`

The nginx container mounts those repo-root relative files directly for TLS termination. The
internal `MOURootCA` stays a client trust concern on managed PCs; the Catalogue does not
need a separate runtime CA file for this setup.

This HTTPS certificate setup is separate from outbound client trust. LDAP and Alvao both use the shared MOU root CA configured by `MOU_ROOT_CA_CERT_PATH`.

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

For dev with observability:

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
The high-level flow lives in [deploy.sh](../deploy.sh); the detailed
environment contract lives in
[scripts/lib/deploy_contract.sh](../scripts/lib/deploy_contract.sh).

Shared requirements for all environments:

- core Django settings such as `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL`, and `HEALTH_DCAT_VERSION`
- env-managed superuser credentials
- all four PostgreSQL database aliases
- `FAIR_GENOMES_SYNC_INTERVAL_HOURS`

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
7. checks `metadata_db` connectivity without running Django migrations against it
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

`metadata_db` is never created or migrated by Django. In production it typically points to an external warehouse-managed database; in development or staging it can point to a stack-local clone exposed through the same alias.

## Auth and admin operations

The env-managed superuser is controlled by:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_PASSWORD`

That account is re-applied on every startup.

Good practice:

- use a username that does not exist in LDAP
- treat it as an env-managed superuser account
- grant real staff access through the Django admin

## Admin access and roles

Roles in practice:

- authenticated user - can browse the catalogue and submit requests
- staff user - can open `/admin/` and `/grafana/`
- superuser - has full Django admin access

If you need another superuser outside the env-managed account:

```bash
./scripts/compose.sh exec web python manage.py createsuperuser
```

## User creation and permissions

On first successful login, Django creates the user automatically in `auth_db`.

New users have no special permissions by default. Grant access through the Django admin by setting:

- `is_staff` for staff and Grafana access
- `is_superuser` for full administrative control
- group memberships for any future role-based permissions

## Observability

The observability stack includes:

- Loki
- Grafana Alloy
- Grafana

Grafana is available at `/grafana/`, but only for logged-in Django staff users. There is no separate Grafana password.

## Metadata compatibility check

Use the bundled HealthData@EU validator when you need a manual HealthDCAT-AP compatibility check for exported metadata.

First export a Turtle file from the running catalogue:

- sign in and download a dataset-specific RDF export from a dataset detail page
- or open `/api/rdf` for the aggregate RDF export

For strict HealthDCAT-AP validation, use an export that includes distributions. HealthDCAT-AP requires every `dcat:Dataset` to reference at least one `dcat:Distribution`.

Start the validator for the configured HealthDCAT-AP release:

```bash
docker compose -f health_dcat_ap/public/releases/release-6/html/shacl/HealthDCAT-AP_validator/docker-compose.yml up -d
```

If `HEALTH_DCAT_VERSION` is not `release-6`, replace `release-6` in the path with the configured release.

Open:

```text
http://localhost:9011/shacl/ehds/upload
```

The root URL `http://localhost:9011/` returns a Tomcat 404; use the `/shacl/ehds/upload` path.

Upload the exported `.ttl` file and select the profile that matches the dataset access rights:

| Access rights URI suffix | Validator profile |
|---|---|
| `PUBLIC` | `public` |
| `RESTRICTED` | `restricted` |
| `NON_PUBLIC` | `non-public` |

Validate mixed-access aggregate exports per profile. The validator profile enforces the matching `dct:accessRights` value for every dataset in the uploaded file.

Treat `sh:Violation` results as compatibility failures. Treat `sh:Warning` results as metadata quality improvements to schedule or document.

## Quality and CI

Run all checks:

```bash
./scripts/check.sh
```
