"""Schema registry access helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from schema_registry import registry
from schema_registry.types import (
    SchemaRegistryContextProfile,
    SchemaRegistryContextTerms,
    SchemaRegistryPayload,
    SchemaRegistryPrefixMap,
)

logger = logging.getLogger(__name__)


def _release_dir() -> Path:
    version: str = getattr(settings, 'HEALTH_DCAT_VERSION', 'release-6')
    base_dir: Path = settings.BASE_DIR
    return base_dir / 'health_dcat_ap' / 'public' / 'releases' / version


def get_schema_dict() -> SchemaRegistryPayload:
    """Return term metadata for the configured HealthDCAT-AP release."""
    return registry.get_registry(_release_dir())


def get_context_prefixes() -> SchemaRegistryPrefixMap:
    """Return the namespace prefixes for the configured HealthDCAT-AP release."""
    return registry.get_namespace_prefixes(_release_dir())


def get_context_terms() -> SchemaRegistryContextTerms:
    """Return named JSON-LD context terms for the configured HealthDCAT-AP release."""
    return registry.get_context_terms(_release_dir())


def get_context_profile() -> SchemaRegistryContextProfile:
    """Return the export context profile for the configured HealthDCAT-AP release."""
    return registry.get_context_profile(_release_dir())
