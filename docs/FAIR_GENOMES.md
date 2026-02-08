# FAIR Genomes Integration

This application integrates with an external FAIR Genomes GraphQL API to sync Personal data into the local database.

## Syncing Data

### Manual Sync

To fetch and sync data from the FAIR Genomes API:

```bash
python manage.py sync_fair_genomes
```

### Dry Run

Test the API connection without saving data:

```bash
python manage.py sync_fair_genomes --dry-run
```

## Configuration

Required environment variables in `.env`:

```bash
FAIR_GENOMES_API_URL=https://api.example.com/graphql
FAIR_GENOMES_API_TOKEN=your-api-token
```

## Scheduling

For production environments, schedule the sync command to run periodically (e.g., via cron):

```bash
# Run daily at 2 AM
0 2 * * * cd /app && python manage.py sync_fair_genomes
```

## Viewing Data

Once synced, Personal records are available at:
- List view: `/fair_genomes/`
- Detail view: `/fair_genomes/<identifier>/`
