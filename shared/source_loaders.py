"""Source-specific loaders for unified catalogue read models and export querysets."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from shared.catalogue_assemblers import build_complete_export_catalogue
from shared.dtos import ExportCatalog, ExportDataset, UnifiedDataset, UnifiedDistribution
from shared.mappers import map_unified_dataset, map_unified_distribution

logger = logging.getLogger(__name__)

_DATASET_SELECT_RELATED = (
    'publisher',
    'contact_point',
    'catalog',
    'hdab',
)
_DISTRIBUTION_SELECT_RELATED = ('dataset_name',)
_EXPORT_DATASET_SELECT_RELATED = (
    'publisher__contact_point',
    'creator__contact_point',
    'contact_point',
    'catalog__publisher__contact_point',
    'hdab__contact_point',
    'custodian__contact_point',
    'source',
)

_ModelTriple = tuple[type[Any], type[Any], type[Any]]


@dataclass(frozen=True)
class SourceConfig:
    app: str
    db_alias: str
    models_loader: Callable[[], _ModelTriple]
    has_table_columns: bool = False

    def load_models(self) -> _ModelTriple:
        return self.models_loader()


def _load_warehouse_models() -> _ModelTriple:
    from warehouse.models import Catalog, Dataset, Distribution

    return Catalog, Dataset, Distribution


def _load_fair_genomes_models() -> _ModelTriple:
    from fair_genomes.models import Catalog, Dataset, Distribution

    return Catalog, Dataset, Distribution


_SOURCE_CONFIGS: tuple[SourceConfig, ...] = (
    SourceConfig(
        app='warehouse',
        db_alias='metadata_db',
        models_loader=_load_warehouse_models,
        has_table_columns=True,
    ),
    SourceConfig(
        app='fair_genomes',
        db_alias='fair_genomes_db',
        models_loader=_load_fair_genomes_models,
    ),
)
_SOURCE_CONFIGS_BY_APP = {config.app: config for config in _SOURCE_CONFIGS}


def _get_source_config(app: str) -> SourceConfig | None:
    config = _SOURCE_CONFIGS_BY_APP.get(app)
    if config is None:
        logger.warning('Unsupported export app requested: %s', app)
    return config


def load_unified_datasets() -> list[UnifiedDataset]:
    results: list[UnifiedDataset] = []
    for config in _SOURCE_CONFIGS:
        try:
            _, dataset_model, _ = config.load_models()
            results.extend(
                map_unified_dataset(dataset, config.app)
                for dataset in dataset_model.objects.using(config.db_alias).select_related(
                    *_DATASET_SELECT_RELATED
                )
            )
        except Exception:  # - preserve tolerant loading across sources
            logger.exception('Failed to load %s datasets', config.app)

    logger.info('Loaded %d datasets', len(results))
    return results


def load_unified_distributions() -> list[UnifiedDistribution]:
    results: list[UnifiedDistribution] = []
    for config in _SOURCE_CONFIGS:
        try:
            _, _, distribution_model = config.load_models()
            results.extend(
                map_unified_distribution(distribution, config.app)
                for distribution in distribution_model.objects.using(
                    config.db_alias
                ).select_related(*_DISTRIBUTION_SELECT_RELATED)
            )
        except Exception:  # - preserve tolerant loading across sources
            logger.exception('Failed to load %s distributions', config.app)

    logger.info('Loaded %d distributions', len(results))
    return results


def get_export_source_apps() -> tuple[str, ...]:
    return tuple(config.app for config in _SOURCE_CONFIGS)


def get_apps_with_table_columns() -> frozenset[str]:
    return frozenset(config.app for config in _SOURCE_CONFIGS if config.has_table_columns)


def get_export_models(app: str):
    config = _get_source_config(app)
    if config is None:
        return None, None, None

    catalog_model, dataset_model, _ = config.load_models()
    return config.db_alias, catalog_model, dataset_model


def build_export_dataset_queryset(app: str, db_alias: str, dataset_model):
    queryset = (
        dataset_model.objects.using(db_alias)
        .select_related(*_EXPORT_DATASET_SELECT_RELATED)
        .prefetch_related('distributions')
    )

    config = _get_source_config(app)
    if config and config.has_table_columns:
        queryset = queryset.prefetch_related('distributions__tables__columns')

    return queryset


def build_export_catalog_queryset(db_alias: str, catalog_model):
    return catalog_model.objects.using(db_alias).select_related('publisher__contact_point')


def load_export_dataset(app: str, name: str) -> ExportDataset | None:
    db_alias, _, dataset_model = get_export_models(app)
    if dataset_model is None or db_alias is None:
        return None

    dataset = build_export_dataset_queryset(app, db_alias, dataset_model).filter(name=name).first()
    if dataset is None:
        return None

    from shared.mappers import map_export_dataset

    return map_export_dataset(dataset, app)


def load_export_catalog(app: str, name: str) -> ExportCatalog | None:
    db_alias, catalog_model, dataset_model = get_export_models(app)
    if catalog_model is None or dataset_model is None or db_alias is None:
        return None

    catalog = build_export_catalog_queryset(db_alias, catalog_model).filter(name=name).first()
    if catalog is None:
        return None

    dataset_queryset = build_export_dataset_queryset(app, db_alias, dataset_model).filter(
        catalog_id=name
    )

    from shared.mappers import map_export_catalog, map_export_dataset

    return map_export_catalog(
        catalog,
        app,
        datasets=[
            map_export_dataset(dataset, app, include_catalog=False) for dataset in dataset_queryset
        ],
    )


def load_complete_export_catalogue() -> tuple[list[ExportCatalog], list[ExportDataset]]:
    return build_complete_export_catalogue(
        apps=get_export_source_apps(),
        get_models=get_export_models,
        get_catalog_queryset=build_export_catalog_queryset,
        get_dataset_queryset=build_export_dataset_queryset,
    )
