"""
Management command to sync Fair Genomes data from GraphQL API.
"""
import logging
from django.core.management.base import BaseCommand, CommandError

from fair_genomes.services import FairGenomesService, FairGenomesAPIException


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync Personal data from Fair Genomes GraphQL API to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch data without saving to database'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no data will be saved'))
        
        try:
            with FairGenomesService() as service:
                self.stdout.write('Connecting to Fair Genomes API...')
                stats = service.sync_personal_data(dry_run=dry_run)
                
            # Output results
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Sync completed successfully:\n'
                    f'  Total records: {stats["total"]}\n'
                    f'  Created: {stats["created"]}\n'
                    f'  Updated: {stats["updated"]}\n'
                    f'  Failed: {stats["failed"]}'
                )
            )
            
        except FairGenomesAPIException as e:
            raise CommandError(f'API error: {e}')
        
        except Exception as e:
            logger.exception('Unexpected error during sync')
            raise CommandError(f'Unexpected error: {e}')

