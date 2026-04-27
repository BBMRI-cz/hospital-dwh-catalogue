"""Typed payloads for HealthDCAT-AP schema registry data."""

from __future__ import annotations

from typing import Literal, TypedDict

SchemaRequirement = Literal['mandatory', 'recommended', 'optional', 'deprecated']


class SchemaRegistryTermDTO(TypedDict):
    prefix: str
    local_name: str
    uri: str
    requirement: SchemaRequirement
    cardinality: str
    label: str
    description: str


SchemaRegistryPayload = dict[str, SchemaRegistryTermDTO]
SchemaRegistryPrefixMap = dict[str, str]
SchemaRegistryContextTerms = dict[str, str]
