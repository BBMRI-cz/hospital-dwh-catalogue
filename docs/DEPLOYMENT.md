# Deployment Guide

## Automated Deployment

Use the automated deploy script for consistent deployments:

```bash
./deploy.sh
```

This script handles:
- Pulling latest code (prod/test environments)
- Stopping old containers
- Building Docker images
- Starting new containers

The Docker entrypoint automatically:
- Runs database migrations
- Compiles translation messages

**Note:** Static files are served from the `warehouse/static/` directory in development. For production, you may need to run `collectstatic` if using a separate static file server.

## Manual Deployment

For manual deployment to production:

1. Ensure `.env` is configured from `.env.prod.example` with `DEPLOY_ENV=prod`

2. Build and start containers:
   ```bash
   docker compose -f docker-compose.prod.yml build
   docker compose -f docker-compose.prod.yml up -d
   ```

3. (Optional) Collect static files if needed:
   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
   ```

**Note:** Migrations run automatically via the entrypoint script when containers start.

## Production Checklist

- [ ] `.env` file configured with secure credentials
- [ ] `SECRET_KEY` is strong and unique
- [ ] Database passwords are secure
- [ ] `DEBUG=False` in production settings
- [ ] HTTPS is configured (if applicable)
- [ ] Database backups are scheduled (see [Backup Guide](BACKUP.md))
- [ ] Backup restore process has been tested
- [ ] Off-site backup storage is configured
