"""Cached schema-registry context loading for export builders."""

from __future__ import annotations

from functools import lru_cache

from schema_registry.types import SchemaRegistryContextProfile
from shared.export_types import JsonLdContext


@lru_cache(maxsize=1)
def get_export_context_prefixes() -> JsonLdContext:
    """Return schema-registry prefixes used by export builders."""
    from schema_registry.services import get_context_prefixes

    return get_context_prefixes()


@lru_cache(maxsize=1)
def get_export_context_terms() -> dict[str, str]:
    """Return named schema-registry context terms used by export builders."""
    from schema_registry.services import get_context_terms

    return get_context_terms()


@lru_cache(maxsize=1)
def get_export_context_profile() -> SchemaRegistryContextProfile:
    """Return the schema-registry context profile used by export builders."""
    from schema_registry.services import get_context_profile

    return get_context_profile()


def clear_export_context_cache() -> None:
    """Clear the cached schema-registry context data for tests."""
    get_export_context_prefixes.cache_clear()
    get_export_context_terms.cache_clear()
    get_export_context_profile.cache_clear()
