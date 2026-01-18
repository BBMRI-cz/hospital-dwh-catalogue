# Quick Setup Guide - Separate Auth Database

## What Changed

Users, groups, permissions, and sessions now live in a dedicated `auth_db` PostgreSQL database instead of the default database.

## Quick Start

### 1. Add to .env

```bash
AUTH_DB_USER=postgres
AUTH_DB_PASSWORD=your_password
AUTH_DB_HOST=db  # or localhost for local development
```

### 2. Recreate Docker Environment

```bash
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Run Migrations

```bash
# Auth database
python manage.py migrate --database=auth_db

# Other databases
python manage.py migrate --database=metadata_db
python manage.py migrate --database=fair_genomes_db
```

### 4. Create Admin User

```bash
python manage.py createsuperuser --database=auth_db
```

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Application Layer                   │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │       AuthRouter (Priority 1)            │  │
│  │  Routes: auth, sessions, admin, content  │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │    WarehouseRouter (Priority 2)          │  │
│  │  Routes: warehouse, fair_genomes         │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬─────────────┐
        ▼             ▼             ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐
   │ auth_db │  │metadata_ │  │ fair_gen │  │default │
   │         │  │   db     │  │ omes_db  │  │(SQLite)│
   ├─────────┤  ├──────────┤  ├──────────┤  ├────────┤
   │ User    │  │ Warehouse│  │ Personal │  │Fallback│
   │ Group   │  │ Tables   │  │ Data     │  │        │
   │ Session │  │ Columns  │  │          │  │        │
   │ Admin   │  │ ...      │  │          │  │        │
   └─────────┘  └──────────┘  └──────────┘  └────────┘
```

## Benefits

✓ **Security**: User credentials isolated from business data  
✓ **Scalability**: Auth DB can scale independently  
✓ **Compliance**: Easier auditing with centralized auth data  
✓ **Maintainability**: Clear separation of concerns  
✓ **Future-proof**: Ready for microservices architecture

## Common Commands

```bash
# Check migrations status
python manage.py showmigrations --database=auth_db

# Create user
python manage.py createsuperuser --database=auth_db

# Shell with specific database
python manage.py dbshell --database=auth_db

# Migrate specific app
python manage.py migrate auth --database=auth_db
```

## Files Modified

- [catalogue/settings/base.py](../catalogue/settings/base.py) - Added auth_db config
- [catalogue/routers.py](../catalogue/routers.py) - Added AuthRouter
- [docker/postgres/initdb.d/init.sql](../docker/postgres/initdb.d/init.sql) - Create auth DB

For complete documentation, see [AUTH_DATABASE_MIGRATION.md](AUTH_DATABASE_MIGRATION.md)
