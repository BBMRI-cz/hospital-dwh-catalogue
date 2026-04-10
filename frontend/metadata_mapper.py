from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import Any

from frontend.presentation_dtos import (
    FrontendDatasetDTO,
    FrontendDcatRow,
    FrontendDistributionDTO,
    FrontendStatChartDTO,
    FrontendStatChartGroupDTO,
    FrontendTableColumnDTO,
    FrontendTableDTO,
)
from schema_registry.types import SchemaRegistryPayload
from shared.dtos import (
    UnifiedDataset,
    UnifiedDistribution,
    UnifiedStatChart,
    UnifiedTable,
    UnifiedTableColumn,
)
from shared.services import derive_status, parse_keywords


def _to_snake(camel: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel).lower()


def distribution_to_dict(distribution: UnifiedDistribution) -> FrontendDistributionDTO:
    return {
        'app': distribution.app,
        'name': distribution.name,
        'title': distribution.title or distribution.name,
        'description': distribution.description,
        'access_url': distribution.access_url,
        'applicable_legislation': distribution.applicable_legislation,
        'format': distribution.format,
        'conforms_to': distribution.conforms_to,
        'byte_size': distribution.byte_size,
        'rights': distribution.rights,
        'release_date': distribution.release_date,
        'modification_date': distribution.modification_date,
        'licence': distribution.licence,
        'db_layer': distribution.db_layer,
    }


def dataset_to_dict(dataset: UnifiedDataset) -> FrontendDatasetDTO:
    return {
        'title': dataset.title or dataset.name,
        'access_rights': dataset.access_rights,
        'version': dataset.version,
        'conforms_to': dataset.conforms_to,
        'theme': dataset.theme,
        'publisher': dataset.publisher,
        'applicable_legislation': dataset.applicable_legislation,
        'health_category': dataset.health_category,
        'hdab': dataset.hdab,
        'source': dataset.source,
        'creator': dataset.creator,
        'issued': dataset.issued,
        'modified': dataset.modified,
        'contact_point': dataset.contact_point,
        'custodian': dataset.custodian,
        'provenance': dataset.provenance,
        'app': dataset.app,
        'name': dataset.name,
        'description': dataset.description,
        'keywords': parse_keywords(dataset.keyword),
        'catalog': dataset.catalog_name,
        'status': derive_status(dataset.access_rights),
        'distributions': [
            distribution_to_dict(distribution) for distribution in dataset.distributions
        ],
    }


def _build_dcat_rows(
    dto_type: type[Any],
    schema_json: SchemaRegistryPayload,
    values: Mapping[str, Any],
) -> list[FrontendDcatRow]:
    field_to_term = {_to_snake(info['local_name']): term for term, info in schema_json.items()}
    return [
        (
            field_to_term[field.name],
            schema_json[field_to_term[field.name]]['label'],
            values.get(field.name),
        )
        for field in dataclasses.fields(dto_type)
        if field.name in field_to_term
    ]


def build_dataset_dcat_rows(
    schema_json: SchemaRegistryPayload,
    dataset: FrontendDatasetDTO,
) -> list[FrontendDcatRow]:
    return _build_dcat_rows(UnifiedDataset, schema_json, dataset)


def build_distribution_dcat_rows(
    schema_json: SchemaRegistryPayload,
    distribution: FrontendDistributionDTO,
) -> list[FrontendDcatRow]:
    return _build_dcat_rows(UnifiedDistribution, schema_json, distribution)


def find_distribution_with_dataset(
    datasets: list[FrontendDatasetDTO],
    app: str,
    name: str,
) -> tuple[FrontendDistributionDTO | None, FrontendDatasetDTO | None]:
    for dataset in datasets:
        for distribution in dataset.get('distributions', []):
            if distribution['app'] == app and distribution['name'] == name:
                return distribution, dataset
    return None, None


def normalise_stat_charts(charts: list[UnifiedStatChart]) -> list[FrontendStatChartDTO]:
    return [
        {
            'label': chart.label,
            'table_name': chart.table_name,
            'column_name': chart.column_name,
            'data': chart.data,
        }
        for chart in charts
    ]


def _normalise_table_columns(
    columns: list[UnifiedTableColumn],
) -> list[FrontendTableColumnDTO]:
    return [
        {
            'name': column.name,
            'title': column.title,
            'description': column.description,
            'datatype': column.datatype,
            'property_url': column.property_url,
        }
        for column in columns
    ]


def normalise_tables(tables: list[UnifiedTable]) -> list[FrontendTableDTO]:
    return [
        {
            'name': table.name,
            'title': table.title,
            'description': table.description,
            'url': table.url,
            'columns': _normalise_table_columns(table.columns),
        }
        for table in tables
    ]


def build_chart_groups(charts: list[FrontendStatChartDTO]) -> list[FrontendStatChartGroupDTO]:
    chart_groups: list[FrontendStatChartGroupDTO] = []
    seen_tables: dict[str, FrontendStatChartGroupDTO] = {}
    for index, chart in enumerate(charts, start=1):
        rendered_chart: FrontendStatChartDTO = {
            'label': chart['label'],
            'table_name': chart['table_name'],
            'column_name': chart['column_name'],
            'data': chart['data'],
            'canvas_idx': index,
        }
        table_name = chart['table_name']
        if table_name not in seen_tables:
            group: FrontendStatChartGroupDTO = {'table_name': table_name, 'charts': []}
            chart_groups.append(group)
            seen_tables[table_name] = group
        seen_tables[table_name]['charts'].append(rendered_chart)
    return chart_groups
