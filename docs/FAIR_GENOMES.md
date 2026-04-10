# FAIR Genomes Integration

The application syncs data from an external FAIR Genomes instance. It fetches dataset and distribution metadata from an RDF (FAIR Data Point) endpoint and aggregation statistics from a MOLGENIS GraphQL API.

## Configuration

Set these variables in your `.env` file:

```bash
FAIR_GENOMES_RDF_URL=https://your-fdp-endpoint.example.com
FAIR_GENOMES_API_URL=https://your-molgenis.example.com/graphql
FAIR_GENOMES_API_TOKEN=your-molgenis-api-token
FAIR_GENOMES_SYNC_INTERVAL_HOURS=24
```

| Variable | Purpose |
|---|---|
| `FAIR_GENOMES_RDF_URL` | FAIR Data Point RDF endpoint for dataset/distribution metadata |
| `FAIR_GENOMES_API_URL` | MOLGENIS GraphQL endpoint for statistics aggregation |
| `FAIR_GENOMES_API_TOKEN` | Authentication token for the MOLGENIS API |
| `FAIR_GENOMES_SYNC_INTERVAL_HOURS` | How often the scheduler runs the sync (in hours, default: 24) |

`FAIR_GENOMES_RDF_URL` and `FAIR_GENOMES_API_URL` can point to different services or hosts.

`FAIR_GENOMES_RDF_URL` must point to a FAIR Data Point/DCAT metadata feed. A generic MOLGENIS schema RDF endpoint such as `/api/rdf` is not sufficient unless it exposes `Catalog`, `Dataset`, `Distribution`, `Agent`, and `ContactPoint` resources.

In development or staging, set `MOCK_FAIR_GENOMES=True` to use sample data instead of connecting to a real API.

## Syncing data

### Manual sync

Run the sync command inside the web container:

```bash
docker compose -f docker-compose.<env>.yml exec web python manage.py sync_fair_genomes
```

This does two things:
1. Fetches dataset and distribution metadata from the RDF endpoint and saves it to the `fair_genomes_db` database
2. Runs GraphQL aggregation queries against MOLGENIS for each active stat definition and saves the results

### Automatic sync (scheduler)

A dedicated `scheduler` Docker container runs the sync on a cron schedule. The interval is controlled by `FAIR_GENOMES_SYNC_INTERVAL_HOURS`. The scheduler always runs one sync immediately in the background when the container starts, then switches to the cron schedule.

The scheduler logs go to the container's stdout, so you can view them with:

```bash
docker compose -f docker-compose.<env>.yml logs scheduler
```

## Viewing the data

Once synced, FAIR Genomes datasets appear in the main catalogue alongside warehouse datasets.

- Dataset detail: `/dataset/fair_genomes/<name>/`
- Distribution detail: `/distribution/fair_genomes/<name>/`
- Dataset detail pages include authenticated UI buttons for dataset-specific JSON-LD and RDF exports.
- Those per-dataset exports are separate from the public aggregate export API and include any nested distribution table/column metadata available for the dataset.
- Aggregate JSON-LD export for all source metadata: `/api/jsonld`
- Aggregate RDF (Turtle) export for all source metadata: `/api/rdf`

Distribution detail pages for FAIR Genomes show statistics charts if stat definitions are configured. See [Stats Setup](STATS.md) for how to configure those.

## Mock data for development or staging

When `MOCK_FAIR_GENOMES=True`, the startup script seeds sample datasets, distributions, contact points, agents, catalogs, stat definitions, and stat results. This lets you see the full UI without connecting to a real MOLGENIS instance.
