"""Typed payloads returned by warehouse service-layer helpers."""

from __future__ import annotations

from typing import TypedDict


class WarehouseTableColumnPayload(TypedDict):
    name: str
    title: str
    description: str
    datatype: str
    property_url: str | None


class WarehouseTablePayload(TypedDict):
    name: str
    title: str
    description: str
    url: str
    columns: list[WarehouseTableColumnPayload]


class WarehouseTableWithStatsPayload(WarehouseTablePayload):
    stats: list[object]


class WarehouseStatChartPayload(TypedDict):
    label: str
    table_name: str
    column_name: str
    data: dict[str, int]
