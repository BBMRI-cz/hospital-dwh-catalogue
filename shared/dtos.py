"""
Unified HealthDCAT-AP Data Transfer Objects (DTOs).

These are plain Python dataclasses — NOT Django models.
They provide a normalised, source-agnostic view of catalogue entities
that can be consumed by views, serialisers, and the API layer without
coupling them to a specific DB model or app.

The `app` field on every DTO carries the originating app label
('warehouse' or 'fair_genomes') so callers can trace provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UnifiedDataset:
    # Required identity fields (no default — must stay first)
    app: str
    name: str
    # DCAT fields — named to match snake_case(schema local_name) so the view
    # can look them up automatically without a separate mapping table.
    title: Optional[str] = None
    access_rights: Optional[str] = None
    version: Optional[str] = None
    conforms_to: Optional[str] = None
    theme: Optional[str] = None
    publisher: Optional[str] = None
    applicable_legislation: Optional[str] = None
    health_category: Optional[str] = None
    hdab: Optional[str] = None
    source: Optional[str] = None       # dct:source — URI of the origin dataset
    rights_holder: Optional[str] = None
    creator: Optional[str] = None
    issued: Optional[str] = None
    modified: Optional[str] = None
    contact_point: Optional[str] = None
    provenance: Optional[str] = None
    # Non-DCAT fields
    description: Optional[str] = None
    keyword: Optional[str] = None
    catalog_name: Optional[str] = None
    # HealthDCAT-AP v6 — new mandatory fields
    identifier: Optional[str] = None   # dct:identifier
    type: Optional[str] = None         # dct:type — EU Dataset-type vocabulary URI(s)
    distributions: list[UnifiedDistribution] = field(default_factory=list)


@dataclass
class UnifiedDistribution:
    app: str
    name: str
    dataset_name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    access_url: Optional[str] = None
    applicable_legislation: Optional[str] = None
    format: Optional[str] = None
    conforms_to: Optional[str] = None
    byte_size: Optional[int] = None
    rights: Optional[str] = None
    issued: Optional[str] = None
    modified: Optional[str] = None
    licence: Optional[str] = None
    # Warehouse-specific; None for FAIR Genomes distributions
    db_layer: Optional[str] = None
