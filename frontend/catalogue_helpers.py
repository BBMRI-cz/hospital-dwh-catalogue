from __future__ import annotations

from typing import cast

from django.core.cache import cache

from frontend.metadata_mapper import dataset_to_dict
from frontend.presentation_dtos import FrontendDatasetDTO
from schema_registry.types import SchemaRegistryPayload
from shared.services import UnifiedCatalogService

CACHE_TTL = 300  # 5 minutes
CATALOGUE_DATASETS_CACHE_KEY = 'catalogue_all_datasets'
CATALOGUE_SCHEMA_CACHE_KEY = 'catalogue_schema_json'


def get_cached_all_datasets(
    *,
    service: UnifiedCatalogService | None = None,
) -> list[FrontendDatasetDTO]:
    """Return cached serialised datasets for frontend catalogue views."""
    all_datasets = cast(
        list[FrontendDatasetDTO] | None,
        cache.get(CATALOGUE_DATASETS_CACHE_KEY),
    )

    if all_datasets is None:
        catalog_service = service or UnifiedCatalogService()
        all_datasets = [
            dataset_to_dict(dataset)
            for dataset in catalog_service.get_datasets_with_distributions()
        ]
        cache.set(CATALOGUE_DATASETS_CACHE_KEY, all_datasets, CACHE_TTL)

    return all_datasets


def get_cached_schema_json(
    *, service: UnifiedCatalogService | None = None
) -> SchemaRegistryPayload:
    """Return cached schema metadata used by frontend templates."""
    catalog_service = service or UnifiedCatalogService()
    schema_json = cast(
        SchemaRegistryPayload | None,
        cache.get_or_set(
            CATALOGUE_SCHEMA_CACHE_KEY,
            catalog_service.get_schema_json,
            CACHE_TTL,
        ),
    )
    empty_schema: SchemaRegistryPayload = {}
    return schema_json or empty_schema


def get_cached_dataset_dict(
    app: str,
    name: str,
    *,
    service: UnifiedCatalogService | None = None,
) -> FrontendDatasetDTO | None:
    """Return a cached serialised dataset dict, or None if no such dataset exists."""
    catalog_service = service or UnifiedCatalogService()
    cache_key = f'dataset:{app}:{name}'
    ds_dict = cast(FrontendDatasetDTO | None, cache.get(cache_key))

    if ds_dict is None:
        dataset, dist_objs = catalog_service.get_single_dataset(app, name)
        if dataset is None:
            return None
        if not dataset.distributions:
            dataset.distributions = dist_objs
        ds_dict = dataset_to_dict(dataset)
        cache.set(cache_key, ds_dict, CACHE_TTL)

    return ds_dict
