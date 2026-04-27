# FAIR Genomes

Audience: operators, staff users, and developers working with the FAIR Genomes integration.

Use this page to configure FAIR Genomes, run syncs, manage statistics, and troubleshoot missing datasets or charts.

## What the integration does

The app syncs FAIR Genomes metadata from two sources:

- an RDF / FAIR Data Point endpoint for catalog, dataset, distribution, agent, and contact-point metadata
- a MOLGENIS GraphQL endpoint for aggregated chart data shown on distribution detail pages

The synced data is stored in `fair_genomes_db` and then merged into the unified catalogue.

## Runtime modes

- `dev` usually keeps `MOCK_FAIR_GENOMES=True`
- `staging` usually connects to a real FAIR Genomes instance
- `prod` uses real FAIR Genomes services only

When `MOCK_FAIR_GENOMES=True`, startup seeds sample datasets, distributions, contact points, agents, catalogs, stat definitions, and stat results.

## Configuration

When `MOCK_FAIR_GENOMES=False`, set:

```bash
FAIR_GENOMES_RDF_URL=https://your-fdp-endpoint.example.com
FAIR_GENOMES_API_URL=https://your-molgenis.example.com/graphql
FAIR_GENOMES_API_TOKEN=your-molgenis-api-token
FAIR_GENOMES_SYNC_INTERVAL_HOURS=24
```

| Variable | Purpose |
|---|---|
| `FAIR_GENOMES_RDF_URL` | RDF / FAIR Data Point endpoint for dataset and distribution metadata |
| `FAIR_GENOMES_API_URL` | MOLGENIS GraphQL endpoint for statistics |
| `FAIR_GENOMES_API_TOKEN` | token used for GraphQL requests |
| `FAIR_GENOMES_SYNC_INTERVAL_HOURS` | scheduler interval in hours |

Notes:

- `FAIR_GENOMES_RDF_URL` and `FAIR_GENOMES_API_URL` can point to different services
- `FAIR_GENOMES_RDF_URL` must expose FAIR Data Point / DCAT resources; a generic MOLGENIS RDF endpoint is not enough unless it exposes the needed catalogue resources

## Sync behavior

A full FAIR Genomes sync does two things:

1. fetches dataset and distribution metadata from RDF
2. runs GraphQL aggregations for active statistics definitions

### Manual sync

```bash
./scripts/compose.sh exec web python manage.py sync_fair_genomes
```

### Automatic sync

The `scheduler` container runs one sync shortly after startup and then continues on the interval defined by `FAIR_GENOMES_SYNC_INTERVAL_HOURS`.

View logs with:

```bash
./scripts/compose.sh logs scheduler
```

## Where the data appears

Once synced, FAIR Genomes data appears in the same UI as warehouse metadata:

- dataset detail: `/dataset/fair_genomes/<name>/`
- distribution detail: `/distribution/fair_genomes/<name>/`
- aggregate exports: `/api/jsonld` and `/api/rdf`

Dataset detail pages can also expose dataset-specific export buttons for logged-in users.

## Statistics

### How statistics work

Two models drive the charts:

- `StatDefinition` — describes which MOLGENIS table and column should be aggregated for a specific FAIR Genomes distribution
- `StatResult` — stores the latest aggregated counts for that table and column

When a sync runs, the app executes MOLGENIS `_groupBy` queries for active `StatDefinition` rows and saves the output into `StatResult`.

Distribution detail pages load those results and render charts grouped by MOLGENIS table.

### Default seeded statistics

A data migration seeds six stat definitions for the `DIST_FG_WES_BAM` distribution:

| Table | Column | Sort order |
|---|---|---|
| sequencing | sequencinginstrumentmodel | 0 |
| sequencing | librarypreparationkit | 1 |
| sequencing | sequencingtype | 2 |
| sample | samplematerialtype | 3 |
| sample | pathologicalstate | 4 |
| genomicdata | genomebuild | 5 |

On a fresh mock setup, the mock seeder creates equivalent sample definitions and results.

### Managing statistics in admin

Go to `/admin/` and open Fair Genomes > Stat definitions.

From there you can:

- add or edit stat definitions
- activate or deactivate charts
- reorder charts with `sort_order`
- run a full FAIR Genomes sync
- re-run only selected statistics

If MOLGENIS schema introspection is available, the admin form offers dropdowns for table and column selection. If it is unavailable, the form falls back to known values already stored in the database.

## Troubleshooting

### FAIR Genomes datasets do not appear

Check:

- `MOCK_FAIR_GENOMES` is set the way you expect
- `fair_genomes_db` is reachable
- the scheduler or manual sync has run
- `FAIR_GENOMES_RDF_URL` points to a real FAIR Data Point / DCAT feed

### Charts are missing on a FAIR Genomes distribution

Check:

- there are active `StatDefinition` rows for that distribution
- a sync has created matching `StatResult` rows
- `FAIR_GENOMES_API_URL` and `FAIR_GENOMES_API_TOKEN` are set when mocks are off

### The admin form does not show live MOLGENIS choices

That usually means schema introspection failed. The form should still work with fallback values, but you should check the GraphQL endpoint and token.

## Related guides

- [USER_GUIDE.md](USER_GUIDE.md)
- [OPERATIONS.md](OPERATIONS.md)
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
