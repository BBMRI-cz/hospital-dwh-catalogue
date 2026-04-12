# Contributing

## Setup

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

This gives you `ruff` (linting and formatting), `mypy` (type checking), and `bandit` (security scanning).

## Workflow

1. Create a branch. Do not push directly to `master`.

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes.

3. Run all checks:

   ```bash
   ./scripts/check.sh
   ```

   This runs linting, formatting, type checking, security scanning, translation checks, the test suite, and a Docker build check. Only commit when everything passes.

4. Commit and push:

   ```bash
   git add .
   git commit -m "feat: description of changes"
   git push origin feature/your-feature-name
   ```

5. Open a pull request on GitHub. Wait for CI to pass, then merge.

## Running individual checks

```bash
./scripts/check-lint.sh          # Ruff linting (auto-fixes)
./scripts/check-format.sh        # Ruff formatting (auto-fixes)
./scripts/check-types.sh         # mypy type checking
./scripts/check-security.sh      # Bandit security scan
./scripts/check-translations.sh  # Translation completeness
./scripts/check-tests.sh         # Django test suite (uses catalogue.settings.ci by default)
./scripts/check-docker.sh        # Docker build check
```

## Code quality requirements

| Check | Tool | Auto-fixable |
|---|---|---|
| Linting | Ruff | Yes |
| Formatting | Ruff | Yes |
| Type checking | mypy | No |
| Security | Bandit | No |

## Frontend stack

The frontend uses server-side Django templates with two lightweight JS libraries vendored under `frontend/static/js/`:

| Library | Version | Purpose |
|---|---|---|
| **HTMX** | 2.0.4 | Server interactions — filtering, pagination, cart toggles, partial page swaps |
| **Alpine.js** | 3.14.9 | Client-side UI state — accordions, dropdowns, inline search, toasts |
| **Chart.js** | latest | Canvas charts for FAIR Genomes stat distributions (imperative, kept as JS) |

**Rules:**
- Use Alpine `x-data` / `x-show` / `@click` for anything that does not need a server round-trip.
- Use HTMX `hx-get` / `hx-post` / `hx-target` for anything that does.
- Do not add new vanilla JavaScript files. If Alpine logic is too complex for a single inline expression, define a named component with `Alpine.data()` in a new static JS file.
- HTMX endpoints that respond to `HX-Request` headers must return rendered HTML partials (not JSON). Views detect the header with `request.headers.get('HX-Request')`.
- Out-of-band swaps (`hx-swap-oob`) are used to update the cart badge alongside button swaps — see `ticketing/views.py` `CartAddView` for the pattern.
- CSRF is passed globally via `hx-headers` on `<body>` in `base.html` — do not add per-request CSRF tokens to HTMX forms.
| Translations | Custom script | No |
| Tests | Django | No |

## Pre-commit hooks (optional)

To run checks automatically on every commit:

```bash
pip install pre-commit
pre-commit install
```

Configuration is in `.pre-commit-config.yaml`. With this set up, you do not need to run `./scripts/check.sh` manually before committing.

## Resetting the development database

To wipe your local database and start fresh:

```bash
docker compose -f docker-compose.dev.yml down -v
```

This deletes all data in the development database.

## CI jobs

| Job | What it checks | If it fails |
|---|---|---|
| Quality Checks | Linting, formatting, types, security | Run `./scripts/check.sh` |
| Translations | Translation files are complete and compiled | Fix `.po` files and recompile |
| Tests | Django test suite | Fix the failing tests |
| CI Success | All above must pass | Fix whichever job failed |

The repository now uses four runtime settings modules:

- `catalogue.settings.dev` for local development
- `catalogue.settings.ci` for automated checks and test execution
- `catalogue.settings.staging` for the deployed pre-production environment
- `catalogue.settings.prod` for production
