"""Cached schema-registry context loading for export builders."""

from __future__ import annotations

from functools import lru_cache

from schema_registry.services import get_context_profile
from schema_registry.types import SchemaRegistryContextProfile


@lru_cache(maxsize=1)
def get_export_context_profile() -> SchemaRegistryContextProfile:
    """Return the schema-registry context profile used by export builders."""
    return get_context_profile()


def clear_export_context_cache() -> None:
    """Clear the cached schema-registry context data for tests."""
    get_export_context_profile.cache_clear()
