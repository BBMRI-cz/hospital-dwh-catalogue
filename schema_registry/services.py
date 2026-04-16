"""Schema registry access helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from schema_registry.registry import get_namespace_prefixes, get_registry
from schema_registry.types import SchemaRegistryPayload, SchemaRegistryPrefixMap

logger = logging.getLogger(__name__)


def _release_dir() -> Path:
    version: str = getattr(settings, 'HEALTH_DCAT_VERSION', 'release-6')
    base_dir: Path = settings.BASE_DIR
    return base_dir / 'health_dcat_ap' / 'public' / 'releases' / version


def get_schema_dict() -> SchemaRegistryPayload:
    """Return term metadata for the configured HealthDCAT-AP release."""
    return get_registry(_release_dir())


def get_context_prefixes() -> SchemaRegistryPrefixMap:
    """Return the namespace prefixes for the configured HealthDCAT-AP release."""
    return get_namespace_prefixes(_release_dir())
