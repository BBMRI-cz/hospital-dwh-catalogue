"""Registered metadata source adapters for the unified catalogue."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fair_genomes.models import (
    Catalog as FairGenomesCatalog,
)
from fair_genomes.models import (
    Dataset as FairGenomesDataset,
)
from fair_genomes.models import (
    Distribution as FairGenomesDistribution,
)
from shared.catalogue_assemblers import build_complete_export_catalogue
from shared.dtos import ExportCatalog, ExportDataset, UnifiedDataset, UnifiedDistribution
from shared.mappers import (
    map_export_catalog,
    map_export_dataset,
    map_unified_dataset,
    map_unified_distribution,
)
from warehouse.models import (
    Catalog as WarehouseCatalog,
)
from warehouse.models import (
    Dataset as WarehouseDataset,
)
from warehouse.models import (
    Distribution as WarehouseDistribution,
)

logger = logging.getLogger(__name__)

DATASET_SELECT_RELATED = (
    'publisher',
    'contact_point',
    'catalog',
    'hdab',
)
DISTRIBUTION_SELECT_RELATED = ('dataset_name',)
EXPORT_DATASET_SELECT_RELATED = (
    'publisher__contact_point',
    'creator__contact_point',
    'contact_point',
    'catalog__publisher__contact_point',
    'hdab__contact_point',
    'custodian__contact_point',
    'source',
)

ModelTriple = tuple[type[Any], type[Any], type[Any]]


@dataclass(frozen=True, slots=True)
class SourceAdapter:
    app: str
    db_alias: str
    models_loader: Callable[[], ModelTriple]
    has_table_columns: bool = False

    @property
    def catalog_model(self):
        catalog_model, _, _ = self.models_loader()
        return catalog_model

    @property
    def dataset_model(self):
        _, dataset_model, _ = self.models_loader()
        return dataset_model

    @property
    def distribution_model(self):
        _, _, distribution_model = self.models_loader()
        return distribution_model

    def unified_datasets(self) -> list[UnifiedDataset]:
        return [
            map_unified_dataset(dataset, self.app)
            for dataset in self.dataset_model.objects.using(self.db_alias).select_related(
                *DATASET_SELECT_RELATED
            )
        ]

    def unified_distributions(self) -> list[UnifiedDistribution]:
        return [
            map_unified_distribution(distribution, self.app)
            for distribution in self.distribution_model.objects.using(self.db_alias).select_related(
                *DISTRIBUTION_SELECT_RELATED
            )
        ]

    def export_dataset_queryset(self):
        queryset = (
            self.dataset_model.objects.using(self.db_alias)
            .select_related(*EXPORT_DATASET_SELECT_RELATED)
            .prefetch_related('distributions')
        )
        if self.has_table_columns:
            queryset = queryset.prefetch_related('distributions__tables__columns')
        return queryset

    def export_catalog_queryset(self):
        return self.catalog_model.objects.using(self.db_alias).select_related(
            'publisher__contact_point'
        )

    def export_dataset(self, name: str) -> ExportDataset | None:
        dataset = self.export_dataset_queryset().filter(name=name).first()
        if dataset is None:
            return None
        return map_export_dataset(dataset, self.app)

    def export_catalog(self, name: str) -> ExportCatalog | None:
        catalog = self.export_catalog_queryset().filter(name=name).first()
        if catalog is None:
            return None

        dataset_queryset = self.export_dataset_queryset().filter(catalog_id=name)
        return map_export_catalog(
            catalog,
            self.app,
            datasets=[
                map_export_dataset(dataset, self.app, include_catalog=False)
                for dataset in dataset_queryset
            ],
        )


def _load_warehouse_models() -> ModelTriple:
    return WarehouseCatalog, WarehouseDataset, WarehouseDistribution


def _load_fair_genomes_models() -> ModelTriple:
    return FairGenomesCatalog, FairGenomesDataset, FairGenomesDistribution


SOURCE_ADAPTERS: tuple[SourceAdapter, ...] = (
    SourceAdapter(
        app='warehouse',
        db_alias='metadata_db',
        models_loader=_load_warehouse_models,
        has_table_columns=True,
    ),
    SourceAdapter(
        app='fair_genomes',
        db_alias='fair_genomes_db',
        models_loader=_load_fair_genomes_models,
    ),
)
SOURCE_ADAPTERS_BY_APP = {adapter.app: adapter for adapter in SOURCE_ADAPTERS}


def get_source_adapter(app: str) -> SourceAdapter | None:
    adapter = SOURCE_ADAPTERS_BY_APP.get(app)
    if adapter is None:
        logger.warning('Unsupported metadata source requested: %s', app)
    return adapter


def get_source_apps() -> tuple[str, ...]:
    return tuple(adapter.app for adapter in SOURCE_ADAPTERS)


def get_apps_with_table_columns() -> frozenset[str]:
    return frozenset(adapter.app for adapter in SOURCE_ADAPTERS if adapter.has_table_columns)


def load_unified_datasets() -> list[UnifiedDataset]:
    results: list[UnifiedDataset] = []
    for adapter in SOURCE_ADAPTERS:
        try:
            results.extend(adapter.unified_datasets())
        except Exception:
            logger.exception('Failed to load %s datasets', adapter.app)

    logger.info('Loaded %d datasets', len(results))
    return results


def load_unified_distributions() -> list[UnifiedDistribution]:
    results: list[UnifiedDistribution] = []
    for adapter in SOURCE_ADAPTERS:
        try:
            results.extend(adapter.unified_distributions())
        except Exception:
            logger.exception('Failed to load %s distributions', adapter.app)

    logger.info('Loaded %d distributions', len(results))
    return results


def load_export_dataset(app: str, name: str) -> ExportDataset | None:
    adapter = get_source_adapter(app)
    return None if adapter is None else adapter.export_dataset(name)


def load_export_catalog(app: str, name: str) -> ExportCatalog | None:
    adapter = get_source_adapter(app)
    return None if adapter is None else adapter.export_catalog(name)


def load_complete_export_catalogue() -> tuple[list[ExportCatalog], list[ExportDataset]]:
    return build_complete_export_catalogue(SOURCE_ADAPTERS)
