"""
UnifiedCatalogService — loads catalogue entities from all source DBs
and returns normalised DTO lists.

This service is the single integration point for views, APIs, or export
scripts that need to consume catalogue data without caring whether it
originates from the Local Metadata (warehouse) or FAIR Genomes DB.
"""

from __future__ import annotations

import logging
from collections import defaultdict

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

    def get_datasets_with_distributions(
        self,
    ) -> list[UnifiedDataset]:
        """
        Return datasets with a ``distributions`` attribute attached to each DTO.

        Each item is a standard UnifiedDataset plus an extra
        ``distributions: list[UnifiedDistribution]`` attribute stapled on so
        that views can pass a single list to the template.
        """
        datasets = self.get_datasets()
        all_dists = self.get_distributions()

        # Group distributions by (app, dataset_name)
        dist_map: dict[tuple[str, str], list[UnifiedDistribution]] = defaultdict(list)
        for d in all_dists:
            if d.dataset_name:
                dist_map[(d.app, d.dataset_name)].append(d)

        for ds in datasets:
            ds.distributions = dist_map.get((ds.app, ds.name), [])

        return datasets

    def get_single_dataset(
        self, app: str, name: str
    ) -> tuple[UnifiedDataset, list[UnifiedDistribution]] | tuple[None, list]:
        """
        Return a (UnifiedDataset, distributions) tuple for a single dataset.

        Returns (None, []) when the dataset is not found.
        """
        datasets = self.get_datasets_with_distributions()
        for ds in datasets:
            if ds.app == app and ds.name == name:
                return ds, ds.distributions
        return None, []

    def get_schema_json(self) -> dict:
        """
        Return a dict keyed by semantics string (e.g. "dct:title") with term
        metadata loaded from the HealthDCAT-AP submodule.

        Used to populate the schema info modal JS in templates.
        Falls back to an empty dict if the submodule release directory is
        missing or rdflib is not installed.
        """
        try:
            from schema_registry.services import get_schema_dict

            return get_schema_dict()
        except Exception:
            logger.exception('Failed to load schema registry')
            return {}
