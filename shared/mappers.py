"""
Mappers: Django model instances → shared DTOs.

Each mapper function accepts a concrete model instance from one of the
source apps and returns a normalised DTO.  FKs are resolved via
getattr(..., None) guards so that None FKs never raise AttributeError.

Naming convention:
  map_<source>_<entity>  e.g. map_warehouse_dataset, map_fair_dataset
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.dtos import (
    UnifiedDataset,
    UnifiedDistribution,
)

if TYPE_CHECKING:
    # Import only for type hints — avoids import-time coupling.
    from warehouse import models as wm
    from fair_genomes import models as fgm


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fk_name(obj: object, fk_attr: str) -> str | None:
    """Return the .name of a FK object, or None if the FK is not set."""
    related = getattr(obj, fk_attr, None)
    return getattr(related, 'name', None) if related else None


def _dt_str(obj: object, attr: str) -> str | None:
    """Return isoformat of a DateTimeField or None."""
    value = getattr(obj, attr, None)
    return value.isoformat() if value else None


# ── Warehouse (Local Metadata) mappers ────────────────────────────────────────

def map_warehouse_dataset(obj: 'wm.Dataset') -> UnifiedDataset:
    cp = getattr(obj, 'contact_point', None)
    return UnifiedDataset(
        app='warehouse',
        name=obj.name,
        title=obj.title,
        has_version=obj.version,
        description=obj.description,
        theme=obj.theme,
        publisher=_fk_name(obj, 'publisher'),
        conforms_to=obj.conforms_to,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        keyword=obj.keyword,
        source=obj.source,
        creator=obj.creator,
        contact_point=getattr(cp, 'email', None),
        rights_holder=obj.rights_holder,
        provenance=obj.provenance,
        catalog_name=_fk_name(obj, 'catalog'),
        access_rights=obj.access_rights,
        applicable_legislation=obj.applicable_legislation,
        health_category=obj.health_category,
        hdab=_fk_name(obj, 'hdab'),
    )


def map_warehouse_distribution(obj: 'wm.Distribution') -> UnifiedDistribution:
    ds = getattr(obj, 'dataset_name', None)
    return UnifiedDistribution(
        app='warehouse',
        name=obj.name,
        dataset_name=getattr(ds, 'name', None),
        title=obj.title,
        description=obj.description,
        access_url=obj.access_url,
        applicable_legislation=obj.applicable_legislation,
        format=obj.format,
        conforms_to=obj.conforms_to,
        byte_size=obj.byte_size,
        rights=obj.rights,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        licence=obj.licence,
        db_layer=getattr(obj, 'db_layer', None),
    )


# ── FAIR Genomes mappers ───────────────────────────────────────────────────────

def map_fair_dataset(obj: 'fgm.Dataset') -> UnifiedDataset:
    cp = getattr(obj, 'contact_point', None)
    return UnifiedDataset(
        app='fair_genomes',
        name=obj.name,
        title=obj.title,
        has_version=obj.version,
        description=obj.description,
        theme=obj.theme,
        publisher=_fk_name(obj, 'publisher'),
        conforms_to=obj.conforms_to,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        keyword=obj.keyword,
        source=obj.source,
        creator=obj.creator,
        contact_point=getattr(cp, 'email', None),
        rights_holder=obj.rights_holder,
        provenance=obj.provenance,
        catalog_name=_fk_name(obj, 'catalog'),
        access_rights=obj.access_rights,
        applicable_legislation=obj.applicable_legislation,
        health_category=obj.health_category,
        hdab=_fk_name(obj, 'hdab'),
    )


def map_fair_distribution(obj: 'fgm.Distribution') -> UnifiedDistribution:
    ds = getattr(obj, 'dataset_name', None)
    return UnifiedDistribution(
        app='fair_genomes',
        name=obj.name,
        dataset_name=getattr(ds, 'name', None),
        title=obj.title,
        description=obj.description,
        access_url=obj.access_url,
        applicable_legislation=obj.applicable_legislation,
        format=obj.format,
        conforms_to=obj.conforms_to,
        byte_size=obj.byte_size,
        rights=obj.rights,
        issued=_dt_str(obj, 'issued'),
        modified=_dt_str(obj, 'modified'),
        licence=obj.licence,
    )
