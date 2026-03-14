"""
Management command to sync Fair Genomes data.

Sync is currently a stub — the GraphQL / MOLGENIS logic was removed during
the HealthDCAT-AP schema migration.  Re-implement FairGenomesService.sync()
to restore functionality.
"""

import logging

from django.core.management.base import BaseCommand

from fair_genomes.services import FairGenomesService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync Fair Genomes catalogue data (currently a stub)'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'Fair Genomes sync is not yet implemented for the new '
                'HealthDCAT-AP schema.  See fair_genomes/services/fair_genomes_service.py.'
            )
        )
        with FairGenomesService() as service:
            result = service.sync()
        self.stdout.write(str(result))
