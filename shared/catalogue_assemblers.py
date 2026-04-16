"""Assemblers that turn service payloads into shared read models."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import replace

from shared.dtos import (
    ExportCatalog,
    ExportDataset,
    UnifiedDataset,
    UnifiedDistribution,
)
from shared.mappers import map_export_catalog, map_export_dataset

logger = logging.getLogger(__name__)


def attach_distributions(
    datasets: list[UnifiedDataset],
    distributions: list[UnifiedDistribution],
) -> list[UnifiedDataset]:
    grouped: dict[tuple[str, str], list[UnifiedDistribution]] = defaultdict(list)
    for distribution in distributions:
        if distribution.dataset_name:
            grouped[(distribution.app, distribution.dataset_name)].append(distribution)

    return [
        replace(
            dataset,
            distributions=[*grouped.get((dataset.app, dataset.name), ())],
        )
        for dataset in datasets
    ]


def build_complete_export_catalogue(
    *,
    apps: tuple[str, ...],
    get_models,
    get_catalog_queryset,
    get_dataset_queryset,
) -> tuple[list[ExportCatalog], list[ExportDataset]]:
    export_catalogs: list[ExportCatalog] = []
    orphan_datasets: list[ExportDataset] = []

    for app in apps:
        db_alias, catalog_model, dataset_model = get_models(app)
        if catalog_model is None or dataset_model is None or db_alias is None:
            continue

        try:
            catalog_rows = list(get_catalog_queryset(db_alias, catalog_model))
            dataset_rows = list(get_dataset_queryset(app, db_alias, dataset_model))
        except Exception:
            logger.exception('Failed to load aggregate export resources for app=%s', app)
            continue

        datasets_by_catalog: dict[str, list[ExportDataset]] = defaultdict(list)
        for dataset in dataset_rows:
            export_dataset = map_export_dataset(dataset, app, include_catalog=False)
            catalog_name = getattr(dataset, 'catalog_id', None)
            if catalog_name:
                datasets_by_catalog[catalog_name].append(export_dataset)
            else:
                orphan_datasets.append(export_dataset)

        export_catalogs.extend(
            map_export_catalog(catalog, app, datasets=datasets_by_catalog.get(catalog.name, []))
            for catalog in catalog_rows
        )

    return export_catalogs, orphan_datasets
