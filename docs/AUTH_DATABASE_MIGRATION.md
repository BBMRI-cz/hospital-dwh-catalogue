# Authentication Database Migration Guide

## Overview

This project now uses a **dedicated authentication database** (`auth_db`) for all user authentication and authorization data, following best practices for separation of concerns and security.

## Architecture

### Database Structure

| Database | Purpose | Models |
|----------|---------|--------|
| `auth_db` | Authentication & Authorization | User, Group, Permission, Session, ContentType, LogEntry |
| `metadata_db` | Warehouse metadata | Warehouse app models |
| `fair_genomes_db` | Fair Genomes data | Fair Genomes app models |
| `default` | Fallback (SQLite) | Development/testing only |

### Benefits

1. **Security Isolation** - User credentials separated from business data
2. **Independent Scaling** - Auth DB can scale independently
3. **Audit & Compliance** - All auth data centralized for security audits
4. **Microservices Ready** - Easy to extract auth as a service later
5. **Separation of Concerns** - Clean architectural boundaries

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Authentication Database
AUTH_DB_ENGINE=django.db.backends.postgresql
AUTH_DB_NAME=hospital_dwh_auth
AUTH_DB_USER=your_db_user
AUTH_DB_PASSWORD=your_db_password
AUTH_DB_HOST=localhost  # or 'db' for Docker
AUTH_DB_PORT=5432
```

### Database Routers

The system uses two routers in order:

1. **AuthRouter** - Routes auth/sessions/admin/contenttypes to `auth_db`
2. **WarehouseRouter** - Routes warehouse/fair_genomes to their respective DBs

## Migration Steps

### Development Environment

1. **Update Environment Variables**
   ```bash
   # Add AUTH_DB_* variables to your .env file
   AUTH_DB_USER=your_username
   AUTH_DB_PASSWORD=your_password
   AUTH_DB_HOST=localhost
   ```

2. **Recreate Docker Containers** (if using Docker)
   ```bash
   docker-compose -f docker-compose.dev.yml down -v
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. **Run Migrations to Auth Database**
   ```bash
   # Migrate auth-related apps to auth_db
   python manage.py migrate --database=auth_db auth
   python manage.py migrate --database=auth_db contenttypes
   python manage.py migrate --database=auth_db sessions
   python manage.py migrate --database=auth_db admin
   ```

4. **Run Migrations to Other Databases**
   ```bash
   # Migrate warehouse app
   python manage.py migrate --database=metadata_db warehouse
   
   # Migrate fair_genomes app
   python manage.py migrate --database=fair_genomes_db fair_genomes
   ```

5. **Create Superuser**
   ```bash
   python manage.py createsuperuser --database=auth_db
   ```

### Migrating Existing User Data

If you have existing users in the old database:

```bash
# Export users from old database
python manage.py dumpdata auth.User auth.Group auth.Permission \
  --database=default --output=users_backup.json

# Load users into new auth database
python manage.py loaddata users_backup.json --database=auth_db
```

### Production Environment

1. **Create Auth Database**
   ```sql
   CREATE DATABASE hospital_dwh_auth;
   GRANT ALL PRIVILEGES ON DATABASE hospital_dwh_auth TO your_db_user;
   ```

2. **Update Production Environment Variables**
   ```bash
   # Update .env or environment configuration
   AUTH_DB_HOST=your-production-db-host
   AUTH_DB_NAME=hospital_dwh_auth
   AUTH_DB_USER=your_production_user
   AUTH_DB_PASSWORD=strong_password_here
   ```

3. **Run Migrations**
   ```bash
   python manage.py migrate --database=auth_db --settings=catalogue.settings.prod
   python manage.py migrate --database=metadata_db --settings=catalogue.settings.prod
   python manage.py migrate --database=fair_genomes_db --settings=catalogue.settings.prod
   ```

4. **Migrate User Data** (if needed)
   ```bash
   # Transfer users from old setup
   python manage.py dumpdata auth contenttypes sessions admin \
     --database=default --output=auth_migration.json
   
   python manage.py loaddata auth_migration.json --database=auth_db
   ```

## Verification

### Check Database Connections

```python
from django.db import connections

# Test auth database
connections['auth_db'].cursor()
print("✓ Auth database connected")

# Test metadata database  
connections['metadata_db'].cursor()
print("✓ Metadata database connected")

# Test fair genomes database
connections['fair_genomes_db'].cursor()
print("✓ Fair Genomes database connected")
```

### Verify User Model Location

```python
from django.contrib.auth.models import User

# Check which database User model uses
from catalogue.routers import AuthRouter
router = AuthRouter()
print(f"User model uses: {router.db_for_read(User)}")
# Should output: auth_db
```

### Check Migrations Status

```bash
# Check auth database migrations
python manage.py showmigrations --database=auth_db

# Check metadata database migrations
python manage.py showmigrations --database=metadata_db

# Check fair genomes database migrations
python manage.py showmigrations --database=fair_genomes_db
```

## Troubleshooting

### Issue: "No such table: auth_user"

**Solution:** Run migrations on the auth database:
```bash
python manage.py migrate --database=auth_db
```

### Issue: Login fails after migration

**Solution:** Ensure session table is in auth_db:
```bash
python manage.py migrate --database=auth_db sessions
```

### Issue: Permission denied errors

**Solution:** Verify database user has correct privileges:
```sql
GRANT ALL PRIVILEGES ON DATABASE hospital_dwh_auth TO your_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
```

### Issue: Relations between databases

**Solution:** The routers prevent cross-database relations. Keep auth models separate from business models. If you need to reference users, use `user_id` (integer) instead of ForeignKey.

## Best Practices

1. **Never store business data in auth_db** - Only auth-related models
2. **Use integer user IDs for references** - Avoid ForeignKey across databases
3. **Regular backups** - Auth database is critical, backup frequently
4. **Monitor connections** - Auth DB will have high connection load
5. **Separate credentials** - Use different DB users for each database
6. **Connection pooling** - Consider pgBouncer for auth_db in production

## Rollback Plan

If you need to rollback to single database:

1. Export all data:
   ```bash
   python manage.py dumpdata --database=auth_db --output=auth_backup.json
   ```

2. Remove `auth_db` from DATABASES in settings

3. Remove `AuthRouter` from DATABASE_ROUTERS

4. Import data to default database:
   ```bash
   python manage.py loaddata auth_backup.json
   ```

## Additional Resources

- [Django Multiple Databases](https://docs.djangoproject.com/en/5.1/topics/db/multi-db/)
- [Database Routers](https://docs.djangoproject.com/en/5.1/topics/db/multi-db/#automatic-database-routing)
- [Migration Commands](https://docs.djangoproject.com/en/5.1/ref/django-admin/#migrate)
