"""
Management command to sync Fair Genomes data from:
  - a FAIR Data Point RDF endpoint  (FAIR_GENOMES_RDF_URL)
  - a MOLGENIS EMX2 GraphQL endpoint (FAIR_GENOMES_API_URL + FAIR_GENOMES_API_TOKEN)

Both sources are synced in one atomic transaction.
Run with --verbosity 0 to suppress the detailed report and only see errors.
"""

import logging

from django.core.cache import cache
from django.core.management.base import BaseCommand

from fair_genomes.services import FairGenomesAPIException, FairGenomesService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Sync Fair Genomes catalogue data from a FAIR Data Point RDF endpoint '
        'and a MOLGENIS EMX2 GraphQL schema endpoint'
    )

    def handle(self, *args, **options):
        try:
            with FairGenomesService() as service:
                report = service.sync()
        except FairGenomesAPIException as exc:
            self.stderr.write(self.style.ERROR(f'Sync failed: {exc}'))
            return

        status = report.get('status', 'unknown')

        if status == 'skipped':
            self.stdout.write(self.style.WARNING(f'Sync skipped: {report.get("reason")}'))
            return

        # ── Summary header ────────────────────────────────────────────────────
        style_fn = self.style.SUCCESS if status == 'complete' else self.style.WARNING
        self.stdout.write(style_fn(f'Sync status: {status.upper()}'))
        self.stdout.write(f'RDF source: {report.get("rdf_url", "")}')
        duration = report.get('duration_seconds')
        if duration is not None:
            self.stdout.write(f'Duration: {duration}s')
        self.stdout.write('')

        # ── Fetched ───────────────────────────────────────────────────────────
        fetched = report.get('fetched', {})
        self.stdout.write('FETCHED FROM RDF:')
        for entity in ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions'):
            names = fetched.get(entity, [])
            label = entity.replace('_', ' ').capitalize()
            self.stdout.write(f'  {label:<18} ({len(names)}): {names}')
        self.stdout.write('')

        # ── Saved ─────────────────────────────────────────────────────────────
        saved = report.get('saved', {})
        self.stdout.write('SAVED:')
        for entity in ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions'):
            created = saved.get(entity, {}).get('created', [])
            updated = saved.get(entity, {}).get('updated', [])
            label = entity.replace('_', ' ').capitalize()
            if created:
                self.stdout.write(self.style.SUCCESS(f'  {label} created: {created}'))
            if updated:
                self.stdout.write(f'  {label} updated: {updated}')
            if not created and not updated:
                self.stdout.write(f'  {label}: nothing saved')
        self.stdout.write('')

        # ── Skipped (unresolved FKs) ──────────────────────────────────────────
        skipped = report.get('skipped', {})
        if skipped:
            self.stdout.write(self.style.WARNING('SKIPPED (unresolved FK references):'))
            for entity, items in skipped.items():
                for item in items:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {entity.capitalize()} '{item['name']}': {item['reason']}"
                        )
                    )
            self.stdout.write('')

        # ── GraphQL sync results ───────────────────────────────────────────────
        graphql_url = report.get('graphql_url')
        graphql_synced = report.get('graphql_synced')

        if graphql_url:
            self.stdout.write('')
            self.stdout.write(f'GRAPHQL SOURCE: {graphql_url}')

        if graphql_synced:
            tables_created = graphql_synced.get('tables', {}).get('created', [])
            tables_updated = graphql_synced.get('tables', {}).get('updated', [])
            cols = graphql_synced.get('columns', {})

            self.stdout.write('GRAPHQL SYNCED:')
            if tables_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Tables created ({len(tables_created)}): {tables_created}'
                    )
                )
            if tables_updated:
                self.stdout.write(f'  Tables updated ({len(tables_updated)}): {tables_updated}')
            if not tables_created and not tables_updated:
                self.stdout.write('  Tables: nothing saved')

            self.stdout.write(
                f'  Columns: {cols.get("created", 0)} created, {cols.get("updated", 0)} updated'
            )

            filtered = report.get('graphql_filtered_out', [])
            if filtered:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Filtered out (ONTOLOGIES, not catalogued) ({len(filtered)}): {filtered}'
                    )
                )

            gql_no_model = report.get('graphql_fields_not_in_model', [])
            if gql_no_model:
                self.stdout.write(
                    '  GraphQL column fields with no model equivalent: ' + ', '.join(gql_no_model)
                )
        elif graphql_url == '':
            self.stdout.write(
                self.style.WARNING(
                    'GRAPHQL: not configured — set FAIR_GENOMES_API_URL to enable table/column sync'
                )
            )

        # ── Stat counts ────────────────────────────────────────────────────────
        stats = report.get('stats')
        if stats is not None:
            self.stdout.write('')
            self.stdout.write('STAT COUNTS:')
            self.stdout.write(
                self.style.SUCCESS(f'  Updated: {stats["updated"]}')
                if stats['updated']
                else f'  Updated: {stats["updated"]}'
            )
            if stats['failed']:
                self.stdout.write(self.style.WARNING(f'  Failed:  {stats["failed"]}'))
                for err in stats['errors']:
                    self.stdout.write(self.style.WARNING(f'    {err}'))

        # Invalidate catalogue cache so fresh data is served immediately.
        cache.delete('catalogue_all_datasets')
