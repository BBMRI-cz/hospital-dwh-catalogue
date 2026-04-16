"""
Management command to sync Fair Genomes data from:
  - a FAIR Data Point RDF endpoint  (FAIR_GENOMES_RDF_URL)
  - a MOLGENIS EMX2 GraphQL endpoint (FAIR_GENOMES_API_URL + FAIR_GENOMES_API_TOKEN)
    for aggregation stats

RDF entities are synced in one atomic transaction.
Aggregation stats run outside the transaction.
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

        style_fn = self.style.SUCCESS if status == 'complete' else self.style.WARNING
        self.stdout.write(style_fn(f'Sync status: {status.upper()}'))
        self.stdout.write(f'RDF source: {report.get("rdf_url", "")}')
        duration = report.get('duration_seconds')
        if duration is not None:
            self.stdout.write(f'Duration: {duration}s')
        self.stdout.write('')

        fetched = report.get('fetched', {})
        self.stdout.write('FETCHED FROM RDF:')
        for entity in ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions'):
            names = fetched.get(entity, [])
            label = entity.replace('_', ' ').capitalize()
            self.stdout.write(f'  {label:<18} ({len(names)}): {names}')
        self.stdout.write('')

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

        graphql_url = report.get('graphql_url')
        if graphql_url:
            self.stdout.write(f'GRAPHQL SOURCE: {graphql_url}')

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

        cache.delete('catalogue_all_datasets')
