# FAIR Genomes

Audience: operators, staff users, and developers working with the FAIR Genomes integration.

Use this page to configure FAIR Genomes, run synchronisation, manage statistics, and troubleshoot missing datasets or charts.

## What the integration does

The app synchronises FAIR Genomes catalogue records and statistics from two technical sources:

- an RDF / FAIR Data Point endpoint for catalog, dataset, distribution, agent, and contact-point metadata
- a MOLGENIS GraphQL endpoint for aggregated chart data shown on distribution detail pages

The synchronised data is stored in `fair_genomes_db` and then merged into the unified catalogue.

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

## Synchronisation behavior

A FAIR Genomes synchronisation run has two phases under one configured interval:

1. RDF metadata phase: fetches catalogue, dataset, distribution, agent, and contact-point metadata from the FAIR Data Point endpoint.
2. Statistics phase: runs MOLGENIS GraphQL aggregations for active `StatDefinition` rows.

The phases are tracked separately in `FairGenomesSyncState`, so staff users can see the last check, last success, last failure, duration, summary, and error message for RDF metadata and statistics independently.

The current implementation always checks the configured RDF endpoint when a synchronisation run starts. It does not currently use ETag, Last-Modified, or payload-hash change detection to skip unchanged RDF parsing.

### Manual synchronisation

```bash
./scripts/compose.sh exec web python manage.py sync_fair_genomes
```

### Automatic synchronisation

The `scheduler` container runs one synchronisation shortly after startup and then continues on the interval defined by `FAIR_GENOMES_SYNC_INTERVAL_HOURS`.

View logs with:

```bash
./scripts/compose.sh logs scheduler
```

## Where the data appears

Once synchronised, FAIR Genomes data appears in the same UI as warehouse metadata:

- dataset detail: `/dataset/fair_genomes/<name>/`
- distribution detail: `/distribution/fair_genomes/<name>/`
- aggregate exports: `/api/jsonld` and `/api/rdf`

Dataset detail pages can also expose dataset-specific export buttons for logged-in users.

## Statistics

### How statistics work

Two models drive the charts:

- `StatDefinition` — describes which MOLGENIS table and column should be aggregated for a specific FAIR Genomes distribution
- `StatResult` — stores the latest aggregated counts for that table and column

When the statistics phase runs, the app executes MOLGENIS `_groupBy` queries for active `StatDefinition` rows and saves the output into `StatResult`.

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

Go to `/admin/` and open FAIR Genomes Integration > Stat definitions.

From there you can:

- add or edit stat definitions
- activate or deactivate charts
- reorder charts with `sort_order`
- save an active stat definition and immediately attempt to synchronise that one aggregation
- run `Check and Synchronise FAIR Genomes`, which synchronises RDF metadata and then refreshes active statistics
- re-run only selected statistics with the admin action

If MOLGENIS schema introspection is available, the admin form offers dropdowns for table and column selection. If it is unavailable, the form falls back to known values already stored in the database.

The stat-definition admin also checks the live RDF endpoint through a short-lived cache. This check is read-only and does not write metadata to the database. It helps staff notice when the live RDF source exposes distributions that have not yet been synchronised locally. If the live RDF check fails, the form falls back to locally synchronised distributions so existing configuration remains editable.

## Troubleshooting

### FAIR Genomes datasets do not appear

Check:

- `MOCK_FAIR_GENOMES` is set the way you expect
- `fair_genomes_db` is reachable
- the scheduler or manual synchronisation has run
- `FAIR_GENOMES_RDF_URL` points to a real FAIR Data Point / DCAT feed
- the FAIR Genomes freshness panel in admin shows a recent successful RDF metadata synchronisation

### Charts are missing on a FAIR Genomes distribution

Check:

- there are active `StatDefinition` rows for that distribution
- the save-time synchronisation, statistics phase, or selected-stat action has created matching `StatResult` rows
- `FAIR_GENOMES_API_URL` and `FAIR_GENOMES_API_TOKEN` are set when mocks are off
- the FAIR Genomes freshness panel in admin shows a recent successful statistics synchronisation

### The admin form does not show live MOLGENIS choices

That usually means schema introspection failed. The form should still work with fallback values, but you should check the GraphQL endpoint and token.

### The admin form does not show new RDF distributions

The form saves only locally synchronised `Distribution` rows. If the live RDF warning says new distributions exist, run `Check and Synchronise FAIR Genomes` first. If the live RDF source is unavailable, the form keeps using locally synchronised distributions.

## Related guides

- [USER_GUIDE.md](USER_GUIDE.md)
- [OPERATIONS.md](OPERATIONS.md)
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
