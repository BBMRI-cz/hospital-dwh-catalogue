"""
Unified HealthDCAT-AP Data Transfer Objects (DTOs).

These are plain Python dataclasses — NOT Django models.
They provide a normalised, source-agnostic view of catalogue entities
that can be consumed by views, serialisers, and the API layer without
coupling them to a specific DB model or app.

The `source` field on every DTO carries the originating app label
('warehouse' or 'fair_genomes') so callers can trace provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UnifiedDataset:
    source: str
    name: str
    title: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    publisher_name: Optional[str] = None
    license: Optional[str] = None
    conformed_to: Optional[str] = None
    issued: Optional[str] = None
    modified: Optional[str] = None
    keyword: Optional[str] = None
    source_uri: Optional[str] = None
    creator: Optional[str] = None
    contact_point_email: Optional[str] = None
    rights_holder: Optional[str] = None
    provenance: Optional[str] = None
    catalog_name: Optional[str] = None
    access_rights: Optional[str] = None
    applicable_legislation: Optional[str] = None
    health_category: Optional[str] = None
    hdab_name: Optional[str] = None
    distributions: list[UnifiedDistribution] = field(default_factory=list)


@dataclass
class UnifiedDistribution:
    source: str
    name: str
    dataset_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    access_url: Optional[str] = None
    applicable_legislation: Optional[str] = None
    format: Optional[str] = None
    conformed_to: Optional[str] = None
    byte_size: Optional[int] = None
    rights: Optional[str] = None
    issued: Optional[str] = None
    modified: Optional[str] = None
    # Warehouse-specific; None for FAIR Genomes distributions
    db_layer: Optional[str] = None
