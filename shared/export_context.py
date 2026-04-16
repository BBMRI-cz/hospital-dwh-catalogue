"""Cached schema-registry context loading for export builders."""

from __future__ import annotations

import logging
from functools import lru_cache

from shared.export_types import JsonLdContext

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_export_context_prefixes() -> JsonLdContext:
    """Return schema-registry prefixes used by export builders."""
    try:
        from schema_registry.services import get_context_prefixes

        return get_context_prefixes()
    except Exception:  # - preserve tolerant export behaviour
        logger.warning(
            'Could not load JSON-LD context prefixes from schema registry',
            exc_info=True,
        )
        return {}


def clear_export_context_cache() -> None:
    """Clear the cached schema-registry prefixes for tests."""
    get_export_context_prefixes.cache_clear()
