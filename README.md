# Hospital Data Warehouse Catalogue

A Django-based web application for browsing and managing hospital data warehouse metadata.

## Quick Start

1. **Setup environment:**
   ```bash
   cp .env.dev.example .env
   ```
   Edit `.env` and set `DEPLOY_ENV=dev`

2. **Start the application:**
   ```bash
   ./deploy.sh
   ```
   Or manually:
   ```bash
   docker compose -f docker-compose.dev.yml up
   ```

3. **Access the application:**
   - Main app: http://localhost:8080/warehouse/catalogue/
   - Admin panel: http://localhost:8080/admin/

## Code Quality Standards

All code **must pass CI checks** before merging. The following checks are enforced:

| Check | Tool | Auto-fixable |
|-------|------|--------------|
| Linting | Ruff | ✅ Yes |
| Formatting | Ruff | ✅ Yes |
| Type Checking | mypy | ❌ Manual |
| Security | Bandit | ❌ Manual |
| Translations | Django | ❌ Manual |

### Running Code Quality Checks Locally

**Before committing**, run the lint script to auto-fix issues:

```bash
# Install dev dependencies (first time only)
pip install -r requirements-dev.txt

# Run all checks with auto-fix
./scripts/lint.sh

# Run checks without auto-fix (same as CI)
./scripts/lint.sh --check
```

The script will:
1. ✅ Auto-fix linting issues (import sorting, simple fixes)
2. ✅ Auto-format code (formatting, whitespace)
3. ❌ Show type errors that need manual fixing
4. ❌ Show security issues that need manual fixing

### Common Issues and Fixes

| Issue | Fix |
|-------|-----|
| `B308: mark_safe()` | Use `format_html()` instead |
| `B608: SQL injection` | Use parameterized queries with `%s` |
| Import order wrong | Auto-fixed by `./scripts/lint.sh` |
| Code not formatted | Auto-fixed by `./scripts/lint.sh` |

### Branch Protection

The `master` and `main` branches are protected:
- ❌ Direct pushes are blocked
- ✅ Pull requests required
- ✅ All CI checks must pass
- ✅ At least one approval required (optional)

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for branch protection setup instructions.

## Documentation

- [Admin Guide](docs/ADMIN.md) - Managing users and content
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Contributing Guide](docs/CONTRIBUTING.md) - Development workflow and branch protection
- [Internationalization](docs/INTERNATIONALIZATION.md) - Adding and updating translations

## Project Structure

- `catalogue/` - Django project settings and configuration
- `warehouse/` - Main warehouse catalogue application
- `fair_genomes/` - FAIR Genomes integration
- `ticketing/` - Ticket request system
- `docker/` - Docker configuration files
- `locale/` - Translation files (i18n)
- `scripts/` - Development utility scripts

