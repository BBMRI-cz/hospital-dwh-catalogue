# Hospital Data Warehouse Catalogue

A Django-based web application for browsing and managing hospital data warehouse metadata.

## Quick Start

1. **Setup environment:**
   ```bash
   cp .env.dev.example .env
   ```

2. **Start the application:**
   ```bash
   sh ./deploy.sh
   ```
   Or manually:
   ```bash
   docker compose -f docker-compose.dev.yml up
   ```

3. **Access the application:**
   - Main app: http://localhost:8080/
   - Admin panel: http://localhost:8080/admin/

4. **Creating users:**
   - First login into the app will create a superuser.
   - Other logins will create new user based on the given username when working in DEV environment.

## Documentation

- [Admin Guide](docs/ADMIN.md) - Managing users and content
- [Authentication Guide](docs/AUTHENTICATION.md) - Complete authentication setup (development and production)
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Contributing Guide](docs/CONTRIBUTING.md) - Development workflow and branch protection
- [Internationalization](docs/INTERNATIONALIZATION.md) - Adding and updating translations
- [FAIR Genomes](docs/FAIR_GENOMES.md) - FAIR Genomes API integration and data sync
- [Ticketing](docs/TICKETING.md) - Alvao Ticketing integration

## Project Structure

- `catalogue/` - Django project settings and configuration
- `warehouse/` - Main warehouse catalogue application
- `fair_genomes/` - FAIR Genomes integration
- `ticketing/` - Ticket request system
- `docs/` - Project documentation
- `docker/` - Docker configuration files
- `locale/` - Translation files (i18n)
- `scripts/` - Development utility scripts
