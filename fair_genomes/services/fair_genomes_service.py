"""
Service layer for Fair Genomes catalogue.

The original GraphQL / MOLGENIS sync logic has been removed while the
FAIR Genomes catalogue is migrated to the HealthDCAT-AP schema.
The class shell is preserved so that the scheduler, management command,
and any future sync implementation can be re-connected without changing
the calling interface.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class FairGenomesAPIException(Exception):
    """Custom exception for Fair Genomes API errors."""

    pass


class FairGenomesService:
    """
    Service class for Fair Genomes catalogue operations.

    Sync functionality is currently a stub pending re-implementation
    against the new HealthDCAT-AP schema.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        timeout: int = 30,
    ):
        self.api_url = api_url or getattr(settings, 'FAIR_GENOMES_API_URL', '')
        self.api_token = api_token or getattr(settings, 'FAIR_GENOMES_API_TOKEN', '')
        self.timeout = timeout

    def sync(self) -> dict[str, str]:
        """
        Stub: sync Fair Genomes data to the local catalogue.

        Will be re-implemented once the HealthDCAT-AP schema migration
        is complete and a new data source / ingestion strategy is agreed.

        Returns:
            {'status': 'not_implemented'}
        """
        logger.warning(
            'FairGenomesService.sync() called but sync is not yet implemented '
            'for the new HealthDCAT-AP schema.'
        )
        return {'status': 'not_implemented'}

    def close(self) -> None:
        """No-op: retained for interface compatibility."""

    def __enter__(self) -> 'FairGenomesService':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
