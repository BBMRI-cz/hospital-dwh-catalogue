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


@lru_cache(maxsize=1)
def get_export_context_terms() -> dict[str, str]:
    """Return named schema-registry context terms used by export builders."""
    try:
        from schema_registry.services import get_context_terms

        return get_context_terms()
    except Exception:  # - preserve tolerant export behaviour
        logger.warning(
            'Could not load JSON-LD context terms from schema registry',
            exc_info=True,
        )
        return {}


def clear_export_context_cache() -> None:
    """Clear the cached schema-registry context data for tests."""
    get_export_context_prefixes.cache_clear()
    get_export_context_terms.cache_clear()
