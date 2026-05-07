"""Unified catalogue service entry points."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable, Mapping
from typing import TypeVar

from fair_genomes.services.catalogue import FairGenomesCatalogueService
from schema_registry.services import get_schema_dict
from schema_registry.types import SchemaRegistryPayload
from shared.catalogue_assemblers import attach_distributions
from shared.dtos import (
    ExportCatalog,
    ExportDataset,
    UnifiedDataset,
    UnifiedDistribution,
    UnifiedStatChart,
    UnifiedTable,
)
from shared.normalization import derive_status, parse_keywords, parse_multi_values
from shared.source_loaders import (
    get_apps_with_table_columns,
    get_source_apps,
    load_complete_export_catalogue,
    load_export_catalog,
    load_export_dataset,
    load_unified_datasets,
    load_unified_distributions,
)
from warehouse.services import WarehouseMetadataService

logger = logging.getLogger(__name__)

__all__ = ['UnifiedCatalogService', 'derive_status', 'parse_keywords', 'parse_multi_values']

_ResultT = TypeVar('_ResultT')


class UnifiedCatalogService:
    """Aggregate catalogue data across source applications."""

    @staticmethod
    def _safe_call(
        operation: Callable[[], _ResultT],
        *,
        default: _ResultT,
        log_message: str,
    ) -> _ResultT:
        try:
            return operation()
        except Exception:
            logger.exception(log_message)
            return default

    @staticmethod
    def _warehouse_service():
        return WarehouseMetadataService()

    @staticmethod
    def _fair_genomes_service():
        return FairGenomesCatalogueService()

    def get_apps_with_table_columns(self) -> frozenset[str]:
        return get_apps_with_table_columns()

    def get_source_apps(self) -> tuple[str, ...]:
        return get_source_apps()

    def get_datasets(self) -> list[UnifiedDataset]:
        return load_unified_datasets()

    def get_distributions(self) -> list[UnifiedDistribution]:
        return load_unified_distributions()

    def get_datasets_with_distributions(self) -> list[UnifiedDataset]:
        return attach_distributions(self.get_datasets(), self.get_distributions())

    def get_single_dataset(
        self,
        app: str,
        name: str,
    ) -> tuple[UnifiedDataset | None, list[UnifiedDistribution]]:
        dataset = next(
            (
                item
                for item in self.get_datasets_with_distributions()
                if item.app == app and item.name == name
            ),
            None,
        )
        if dataset is not None:
            return dataset, dataset.distributions
        logger.warning('Dataset not found: app=%s name=%s', app, name)
        return None, []

    def get_schema_json(self) -> SchemaRegistryPayload:
        return self._safe_call(
            self._load_schema_json,
            default={},
            log_message='Failed to load schema registry',
        )

    @staticmethod
    def _load_schema_json() -> SchemaRegistryPayload:
        return get_schema_dict()

    def get_dataset_names_by_columns(self, column_titles: set[str]) -> frozenset[str]:
        if not column_titles:
            return frozenset()
        return self._safe_call(
            lambda: self._warehouse_service().get_dataset_names_by_columns(column_titles),
            default=frozenset(),
            log_message='Failed to resolve dataset names by columns',
        )

    def build_column_counter(
        self,
        filtered_dist_names: list[str],
        dist_to_dataset: Mapping[str, str],
    ) -> Counter[str]:
        if not filtered_dist_names:
            return Counter()
        return self._safe_call(
            lambda: self._warehouse_service().build_column_counter(
                filtered_dist_names,
                dist_to_dataset,
            ),
            default=Counter(),
            log_message='Failed to build column counter',
        )

    def get_tables_with_columns(self, app: str, distribution_name: str) -> list[UnifiedTable]:
        if app not in get_apps_with_table_columns():
            return []
        return self._safe_call(
            lambda: self._warehouse_service().get_tables_with_columns(distribution_name),
            default=[],
            log_message=f'Failed to load warehouse tables for distribution={distribution_name}',
        )

    def get_stat_charts(self, app: str, distribution_name: str) -> list[UnifiedStatChart]:
        if app != 'fair_genomes':
            return []
        return self._safe_call(
            lambda: self._fair_genomes_service().get_stat_charts(distribution_name),
            default=[],
            log_message=f'Failed to load stat charts for distribution={distribution_name}',
        )

    def get_export_dataset(self, app: str, name: str) -> ExportDataset | None:
        export_dataset = load_export_dataset(app, name)
        if export_dataset is None:
            logger.warning('Export dataset not found: app=%s name=%s', app, name)
            return None
        return export_dataset

    def get_export_catalog(self, app: str, name: str) -> ExportCatalog | None:
        export_catalog = load_export_catalog(app, name)
        if export_catalog is None:
            logger.warning('Export catalog not found: app=%s name=%s', app, name)
            return None
        return export_catalog

    def get_complete_export_catalogue(self) -> tuple[list[ExportCatalog], list[ExportDataset]]:
        return self._safe_call(
            load_complete_export_catalogue,
            default=([], []),
            log_message='Failed to load aggregate export resources',
        )
