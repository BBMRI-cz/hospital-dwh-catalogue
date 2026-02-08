# Contributing Guide

This document describes the development workflow and code quality requirements for the Hospital Data Warehouse Catalogue project.

## Development Workflow

### 1. Install Development Dependencies

First time setup - install development tools:

```bash
pip install -r requirements-dev.txt
```

This installs:
- `ruff` - Linting and formatting
- `mypy` - Type checking
- `bandit` - Security scanning

### 2. Create a Feature Branch

Never push directly to `master`. Always create a feature branch:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 3. Make Your Changes

Write your code.

### 4. Run Code Quality Checks

Before committing, **always run the lint script**:

```bash
./scripts/lint.sh
```

This will:
- Auto-fix linting issues
- Auto-format your code
- Show type errors (fix manually)
- Show security issues (fix manually)

**Only commit when all checks pass!**

### 4. Commit and Push

```bash
git add .
git commit -m "feat: description of your changes"
git push origin feature/your-feature-name
```

### 5. Create a Pull Request

1. Go to GitHub and create a Pull Request
2. Wait for CI checks to pass
4. Merge when passed

---

## Code Quality Requirements

All code must pass these checks before merging:

| Check          | Tool   | Command                                           | Auto-fixable |
|----------------|--------|---------------------------------------------------|--------------|
| Linting        | Ruff   | `ruff check .`                                    | Yes          |
| Formatting     | Ruff   | `ruff format --check .`                           | Yes          |
| Type Checking  | mypy   | `mypy .`                                          | No           |
| Security       | Bandit | `bandit -r . -x ./warehouse/static,./venv -ll`    | No           |
| Tests          | Django | `python manage.py test`                           | No           |

## Pre-commit Hooks (Optional)

For automatic checks before each commit, install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

This will run checks automatically when you run `git commit`.

Configuration is in `.pre-commit-config.yaml`.

Thanks to this you do not have to run the `./lint.sh` manually.

---

## Docker Development

### Clearing Database Volumes

If you need to reset your development database to a clean state:

```bash
# Stop and remove containers with volumes
docker compose -f docker-compose.dev.yml down -v

# Or remove specific volume
docker volume rm hospital_dwh_postgres_data_dev
```

**Warning:** This will delete all data in your development database.

---

## CI Jobs

| Job              | Description                   | Failure Action                             |
|------------------|-------------------------------|--------------------------------------------|
| Lint & Format    | Checks code style             | Run `./scripts/lint.sh`                    |
| Type Checking    | Validates type hints          | Fix type errors manually                   |
| Translations     | Checks i18n files             | Run `python manage.py makemessages`        |
| Security         | Scans for vulnerabilities     | Fix security issues manually               |
| Tests            | Runs the test suite           | Fix failing tests                          |
| CI Success       | Final gate                    | All above must pass                        |
