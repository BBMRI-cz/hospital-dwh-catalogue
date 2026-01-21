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

## Documentation

- [Admin Guide](docs/ADMIN.md) - Managing users and content
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Backup Guide](docs/BACKUP.md) - Database backup and restore procedures
- [Internationalization](docs/INTERNATIONALIZATION.md) - Adding and updating translations

## Project Structure

- `catalogue/` - Django project settings and configuration
- `warehouse/` - Main warehouse catalogue application
- `fair_genomes/` - FAIR Genomes integration
- `docker/` - Docker configuration files
- `locale/` - Translation files (i18n)

