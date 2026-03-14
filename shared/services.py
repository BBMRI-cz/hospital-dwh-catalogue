"""
UnifiedCatalogService — loads catalogue entities from all source DBs
and returns normalised DTO lists.

This service is the single integration point for views, APIs, or export
scripts that need to consume catalogue data without caring whether it
originates from the Local Metadata (warehouse) or FAIR Genomes DB.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.dtos import UnifiedDataset, UnifiedDistribution
from shared.mappers import (
    map_fair_dataset,
    map_fair_distribution,
    map_warehouse_dataset,
    map_warehouse_distribution,
)

logger = logging.getLogger(__name__)


class UnifiedCatalogService:
    """
    Aggregates catalogue data from all registered source apps.

    Usage::

        service = UnifiedCatalogService()
        datasets = service.get_datasets()
        distributions = service.get_distributions()
    """

    def get_datasets(self) -> list[UnifiedDataset]:
        """
        Return a merged list of UnifiedDataset DTOs from all sources.

        Sources are queried lazily so that a failure in one DB does not
        prevent data from the other from being returned.
        """
        results: list[UnifiedDataset] = []

        # ── Local Metadata (warehouse) ──────────────────────────────────────
        try:
            from warehouse.models import Dataset as WarehouseDataset

            results.extend(
                map_warehouse_dataset(obj)
                for obj in WarehouseDataset.objects.using('metadata_db').select_related(
                    'publisher', 'contact_point', 'catalog', 'hdab'
                )
            )
        except Exception:
            logger.exception('Failed to load warehouse datasets')

        # ── FAIR Genomes ────────────────────────────────────────────────────
        try:
            from fair_genomes.models import Dataset as FairDataset

            results.extend(
                map_fair_dataset(obj)
                for obj in FairDataset.objects.using('fair_genomes_db').select_related(
                    'publisher', 'contact_point', 'catalog', 'hdab'
                )
            )
        except Exception:
            logger.exception('Failed to load fair_genomes datasets')

        return results

    def get_distributions(self) -> list[UnifiedDistribution]:
        """
        Return a merged list of UnifiedDistribution DTOs from all sources.
        """
        results: list[UnifiedDistribution] = []

        try:
            from warehouse.models import Distribution as WarehouseDistribution

            results.extend(
                map_warehouse_distribution(obj)
                for obj in WarehouseDistribution.objects.using('metadata_db').select_related(
                    'dataset_name'
                )
            )
        except Exception:
            logger.exception('Failed to load warehouse distributions')

        try:
            from fair_genomes.models import Distribution as FairDistribution

            results.extend(
                map_fair_distribution(obj)
                for obj in FairDistribution.objects.using('fair_genomes_db').select_related(
                    'dataset_name'
                )
            )
        except Exception:
            logger.exception('Failed to load fair_genomes distributions')

        return results
