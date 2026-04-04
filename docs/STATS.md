# Stats Setup

Statistics show aggregated data from MOLGENIS as charts on FAIR Genomes distribution detail pages. Each chart shows the count of distinct values for a specific table/column pair in MOLGENIS (for example, how many samples used each sequencing instrument model).

## How it works

There are two models involved:

- `StatDefinition` -- defines what to query. Links a FAIR Genomes distribution to a MOLGENIS table and column. Has a display label, sort order, and an active/inactive flag.
- `StatResult` -- stores the query result. Contains a JSON object mapping values to counts (for example, `{"MiSeq": 87, "NovaSeq": 42}`) and a timestamp of the last sync.

When a sync runs, the application iterates over all active `StatDefinition` rows, sends a GraphQL `_groupBy` aggregation query to MOLGENIS for each one, and saves the result as a `StatResult`.

The distribution detail page reads the stat results and renders them as charts, grouped by MOLGENIS table.

## Default stat definitions

A data migration (`fair_genomes/migrations/0002_seed_stat_definitions.py`) seeds six stat definitions for the `DIST_FG_WES_BAM` distribution:

| Table | Column | Sort order |
|---|---|---|
| sequencing | sequencinginstrumentmodel | 0 |
| sequencing | librarypreparationkit | 1 |
| sequencing | sequencingtype | 2 |
| sample | samplematerialtype | 3 |
| sample | pathologicalstate | 4 |
| genomicdata | genomebuild | 5 |

These are only created if the `DIST_FG_WES_BAM` distribution already exists in the database. On a fresh install with mock data, the mock seeder creates them instead.

## Adding a new stat definition

### Through the admin panel

1. Go to `/admin/` and navigate to Fair Genomes > Stat definitions
2. Click "Add stat definition"
3. Fill in the fields:
   - Distribution -- which FAIR Genomes distribution this chart belongs to
   - MOLGENIS table -- the table name in MOLGENIS (if MOLGENIS is reachable, this is a dropdown; otherwise a text field)
   - MOLGENIS column -- the column name within that table (same dropdown/text behavior)
   - Display label -- optional label shown above the chart (if blank, the column name is used)
   - Sort order -- controls the order of charts on the distribution page
   - Is active -- uncheck to hide the chart without deleting the definition
4. Save

The table and column dropdowns are populated by introspecting the MOLGENIS GraphQL schema. If MOLGENIS is not reachable, they fall back to plain text inputs. The schema is cached for 5 minutes.

### Through the data migration

To add definitions that should exist on every deployment, add them to the seed migration or create a new data migration in `fair_genomes/migrations/`.

## Syncing stats

Stats are synced as part of the FAIR Genomes sync process. You can trigger it in several ways:

### From the admin panel

1. Go to Fair Genomes > Stat definitions
2. Click the "Full Sync" button at the top of the list

This runs a full sync (RDF metadata fetch + GraphQL stats). Only superusers can trigger this.

To sync only specific stats:

1. Select the stat definitions you want to sync using the checkboxes
2. From the action dropdown, choose "Sync selected stats" and click Go

### From the command line

Run the full sync:

```bash
docker compose -f docker-compose.<env>.yml exec web python manage.py sync_fair_genomes
```

### Automatically via the scheduler

The `scheduler` container runs the sync on a cron schedule controlled by `FAIR_GENOMES_SYNC_INTERVAL_HOURS` (default: 24 hours). See [FAIR Genomes](FAIR_GENOMES.md) for configuration.

## Deactivating a stat

Go to the stat definitions list in the admin panel. The "Is active" column is editable inline. Uncheck it and save. The chart will no longer appear on the distribution page, and the stat will be skipped during sync.

## How charts are displayed

On a distribution detail page (`/distribution/fair_genomes/<name>/`), the application:

1. Finds all active `StatDefinition` rows for that distribution
2. Loads matching `StatResult` rows
3. Groups the charts by MOLGENIS table
4. Renders each chart with its label and value/count data

If there are no active stat definitions or no stat results for a distribution, no charts section is shown.

## Mock data for development

When `MOCK_FAIR_GENOMES=True`, the mock seeder (`seed_fair_genomes_mock` management command) creates sample stat definitions and stat results with realistic-looking data. This runs automatically on container startup.

## Required environment variables

Stats need the MOLGENIS API connection to work:

```bash
FAIR_GENOMES_API_URL=https://your-molgenis.example.com/graphql
FAIR_GENOMES_API_TOKEN=your-molgenis-api-token
```

Without these, the sync will fail for stats (though RDF metadata can still sync if `FAIR_GENOMES_RDF_URL` is set).
