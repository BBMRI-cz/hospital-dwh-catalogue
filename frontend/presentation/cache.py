"""Cache-backed catalogue snapshot loaders for the frontend presentation layer."""

from __future__ import annotations

from typing import cast

from django.core.cache import cache

from frontend.presentation.mapping import build_catalogue_snapshot
from frontend.presentation.types import (
    CatalogueDistributionLookup,
    CatalogueSnapshot,
    FrontendDataset,
)
from schema_registry.types import SchemaRegistryPayload
from shared.services import UnifiedCatalogService

CACHE_TTL = 300
CATALOGUE_SNAPSHOT_CACHE_KEY = 'catalogue_snapshot'
CATALOGUE_SCHEMA_CACHE_KEY = 'catalogue_schema_json'


def get_cached_catalogue_snapshot(
    *,
    service: UnifiedCatalogService | None = None,
) -> CatalogueSnapshot:
    snapshot = cast(CatalogueSnapshot | None, cache.get(CATALOGUE_SNAPSHOT_CACHE_KEY))
    if snapshot is not None:
        return snapshot

    catalog_service = service or UnifiedCatalogService()
    snapshot = build_catalogue_snapshot(catalog_service.get_datasets_with_distributions())
    cache.set(CATALOGUE_SNAPSHOT_CACHE_KEY, snapshot, CACHE_TTL)
    return snapshot


def get_cached_schema_json(
    *,
    service: UnifiedCatalogService | None = None,
) -> SchemaRegistryPayload:
    catalog_service = service or UnifiedCatalogService()
    schema_json = cast(
        SchemaRegistryPayload | None,
        cache.get_or_set(CATALOGUE_SCHEMA_CACHE_KEY, catalog_service.get_schema_json, CACHE_TTL),
    )
    empty_schema: SchemaRegistryPayload = {}
    return schema_json or empty_schema


def get_cached_dataset(
    app: str,
    name: str,
    *,
    service: UnifiedCatalogService | None = None,
) -> FrontendDataset | None:
    snapshot = get_cached_catalogue_snapshot(service=service)
    return snapshot.datasets_by_key.get((app, name))


def get_cached_distribution_lookup(
    app: str,
    name: str,
    *,
    service: UnifiedCatalogService | None = None,
) -> CatalogueDistributionLookup | None:
    snapshot = get_cached_catalogue_snapshot(service=service)
    return snapshot.distributions_by_key.get((app, name))
