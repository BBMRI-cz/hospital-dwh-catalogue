# Contributing Guide

This document describes the development workflow and code quality requirements for the Hospital Data Warehouse Catalogue project.

## Development Workflow

### 1. Create a Feature Branch

Never push directly to `master` or `main`. Always create a feature branch:

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

Write your code following the project conventions (see [Copilot Instructions](../.github/copilot-instructions.md)).

### 3. Run Code Quality Checks

Before committing, **always run the lint script**:

```bash
./scripts/lint.sh
```

This will:
- ✅ Auto-fix linting issues
- ✅ Auto-format your code
- ❌ Show type errors (fix manually)
- ❌ Show security issues (fix manually)

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
3. Request review if required
4. Merge when approved

---

## Code Quality Requirements

All code must pass these checks before merging:

| Check | Tool | Command | Auto-fixable |
|-------|------|---------|--------------|
| Linting | Ruff | `ruff check .` | ✅ `ruff check . --fix` |
| Formatting | Ruff | `ruff format --check .` | ✅ `ruff format .` |
| Type Checking | mypy | `mypy .` | ❌ Manual |
| Security | Bandit | `bandit -r . -x ./warehouse/static,./venv -ll` | ❌ Manual |

### Common Fixes

#### B308: mark_safe() vulnerability
```python
# ❌ Bad - flagged by Bandit
from django.utils.safestring import mark_safe
return mark_safe('<b>Hello</b>')

# ✅ Good - use format_html instead
from django.utils.html import format_html
return format_html('<b>{}</b>', 'Hello')
```

#### B608: SQL injection
```python
# ❌ Bad - flagged by Bandit
cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

# ✅ Good - use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

#### Type errors
```python
# ❌ Bad - mypy error: incompatible return type
def get_name(self) -> str:
    return self.name  # name might be None

# ✅ Good - handle None case
def get_name(self) -> str:
    return self.name or ''
```

---

## Setting Up Branch Protection (GitHub)

To prevent direct pushes to `master`/`main` and require CI checks:

### Step 1: Go to Repository Settings

1. Navigate to your GitHub repository
2. Click **Settings** → **Branches**

### Step 2: Add Branch Protection Rule

1. Click **Add branch protection rule**
2. Branch name pattern: `master` (or `main`)

### Step 3: Configure Protection Rules

Enable these settings:

- [x] **Require a pull request before merging**
  - [x] Require approvals: `1` (optional, for team projects)
  - [x] Dismiss stale pull request approvals when new commits are pushed

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - Search and add these status checks:
    - `🔍 Lint & Format`
    - `🔷 Type Checking`
    - `🌐 Translations`
    - `🔒 Security`
    - `✅ CI Success`

- [x] **Do not allow bypassing the above settings**

- [ ] **Require signed commits** (optional)

- [x] **Include administrators** (recommended)

### Step 4: Save Changes

Click **Create** or **Save changes**.

### Result

After setup:
- ❌ Direct `git push origin master` will be rejected
- ✅ Pull requests will require all CI checks to pass
- ✅ Code quality is enforced automatically

---

## Pre-commit Hooks (Optional)

For automatic checks before each commit, install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

This will run checks automatically when you run `git commit`.

Configuration is in `.pre-commit-config.yaml`.

---

## Continuous Integration

The CI pipeline runs on every push and pull request to `master`, `main`, and `develop`.

### CI Jobs

| Job | Description | Failure Action |
|-----|-------------|----------------|
| 🔍 Lint & Format | Checks code style | Run `./scripts/lint.sh` |
| 🔷 Type Checking | Validates type hints | Fix type errors manually |
| 🌐 Translations | Checks i18n files | Run `python manage.py makemessages` |
| 🔒 Security | Scans for vulnerabilities | Fix security issues manually |
| ✅ CI Success | Final gate | All above must pass |

### Viewing CI Results

1. Go to your PR or commit on GitHub
2. Click the **Checks** tab or status icon
3. Expand failed jobs to see details
4. Follow the suggested fixes in the output

---

## Questions?

If you have questions about the workflow or code standards, check:
- [Copilot Instructions](../.github/copilot-instructions.md)
- [Django Patterns](../.github/instructions/01-django-patterns.instructions.md)
