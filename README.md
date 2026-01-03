# Hospital Data Warehouse Catalogue

A Django-based web application for browsing and managing hospital data warehouse metadata.

## Prerequisites 

- **Docker Desktop** - [Docker Website](https://www.docker.com/products/docker-desktop)
- **Git** (optional)

## Environment Configuration

Before running the application, create a `.env` file from the appropriate template:

**For local development:**
```bash
cp .env.dev.example .env
```

**For test server:**
```bash
cp .env.test.example .env
```

**For production:**
```bash
cp .env.prod.example .env
```

Then edit the `.env` file and update the values (especially `SECRET_KEY` and database passwords).

**Never commit the `.env` file** - it's already in `.gitignore` and contains sensitive credentials.

## Running the application

The application supports three environments: development, testing, and production.

### Development Environment

For local development with live code reloading:

```bash
docker-compose -f docker-compose.dev.yml up
```

Development uses the `.env` file you created from `.env.dev.example`.

### Test Environment

For remote testing server:

```bash
docker-compose -f docker-compose.test.yml up
```

Ensure you created `.env` from `.env.test.example` with proper test server credentials.

### Production Environment

For production deployment:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Ensure you created `.env` from `.env.prod.example` with secure production credentials.

### Accessing the Application

Open browser and navigate to:
```
http://localhost:8080/warehouse/catalogue/
```

## Admin Page

The Django admin interface provides a powerful way to manage the data warehouse catalogue content.

### Accessing the Admin Panel

Navigate to:
```
http://localhost:8080/admin/
```

### Creating an Admin User

To access the admin panel, you need to create a superuser account. Run this command:

```bash
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser
```

Follow the prompts to enter:
- Username
- Email address (optional)
- Password (enter twice for confirmation)

Replace `docker-compose.dev.yml` with the appropriate file for your environment

## Sample data

The application includes generated mock data for development and testing.

## Internationalization (i18n)

The application supports multiple languages (currently Czech and English).

### Updating Translations

When developing and adding or modifying translatable strings:

1. **Extract new strings** from your code to `.po` files:
   ```bash
   python manage.py makemessages --all
   ```

2. **Edit the `.po` files** in `locale/cs/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` to add translations.

3. **For local development** (outside Docker), compile translations:
   ```bash
   python manage.py compilemessages
   ```

4. **Commit only `.po` files** to git. The `.mo` files are automatically generated in Docker and excluded from version control.

## Deployment

Use the automated deploy script for consistent deployments:

```bash
./deploy.sh
```

## Stopping the application

```bash
docker-compose -f docker-compose.dev.yml down
```

To also delete the database volume (fresh start):

```bash
docker-compose -f docker-compose.dev.yml down -v
```

Replace `docker-compose.dev.yml` with the appropriate file for your environment.
