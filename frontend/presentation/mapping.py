"""Mapping helpers for frontend presentation models."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from frontend.presentation.types import (
    CatalogueDistributionLookup,
    CatalogueSnapshot,
    FrontendDataset,
    FrontendDcatRow,
    FrontendDistribution,
    FrontendStatChart,
    FrontendStatChartGroup,
    FrontendTable,
    FrontendTableColumn,
)
from schema_registry.types import SchemaRegistryPayload
from shared.dtos import UnifiedDataset, UnifiedDistribution, UnifiedStatChart, UnifiedTable
from shared.normalization import derive_status, parse_keywords, parse_multi_values


def _to_snake(camel: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel).lower()


def _build_search_text(dataset: FrontendDataset) -> str:
    distribution_titles = [distribution.title for distribution in dataset.distributions]
    distribution_conforms_to = [
        item for distribution in dataset.distributions for item in distribution.conforms_to
    ]
    distribution_legislation = [
        item
        for distribution in dataset.distributions
        for item in distribution.applicable_legislation
    ]
    return ' '.join(
        [
            dataset.title or '',
            dataset.identifier or '',
            ' '.join(dataset.type),
            ' '.join(dataset.conforms_to),
            ' '.join(dataset.theme),
            dataset.description or '',
            dataset.custodian or '',
            dataset.source or '',
            ' '.join(dataset.applicable_legislation),
            ' '.join(dataset.health_category),
            ' '.join(dataset.keywords),
            ' '.join(distribution_titles),
            ' '.join(distribution_conforms_to),
            ' '.join(distribution_legislation),
        ]
    ).lower()


def distribution_to_view_model(distribution: UnifiedDistribution) -> FrontendDistribution:
    return FrontendDistribution(
        app=distribution.app,
        name=distribution.name,
        title=distribution.title or distribution.name,
        description=distribution.description,
        access_url=distribution.access_url,
        applicable_legislation=parse_multi_values(distribution.applicable_legislation),
        format=distribution.format,
        conforms_to=parse_multi_values(distribution.conforms_to),
        byte_size=distribution.byte_size,
        rights=distribution.rights,
        release_date=distribution.release_date,
        modification_date=distribution.modification_date,
        licence=distribution.licence,
        db_layer=distribution.db_layer,
    )


def dataset_to_view_model(dataset: UnifiedDataset) -> FrontendDataset:
    view_model = FrontendDataset(
        app=dataset.app,
        name=dataset.name,
        title=dataset.title or dataset.name,
        identifier=dataset.identifier,
        type=parse_multi_values(dataset.type),
        access_rights=dataset.access_rights,
        version=dataset.version,
        conforms_to=parse_multi_values(dataset.conforms_to),
        theme=parse_multi_values(dataset.theme),
        publisher=dataset.publisher,
        applicable_legislation=parse_multi_values(dataset.applicable_legislation),
        health_category=parse_multi_values(dataset.health_category),
        hdab=dataset.hdab,
        source=dataset.source,
        creator=dataset.creator,
        issued=dataset.issued,
        modified=dataset.modified,
        contact_point=dataset.contact_point,
        custodian=dataset.custodian,
        provenance=dataset.provenance,
        description=dataset.description,
        keywords=parse_keywords(dataset.keyword),
        catalog_name=dataset.catalog_name,
        status=derive_status(dataset.access_rights),
        distributions=[
            distribution_to_view_model(distribution) for distribution in dataset.distributions
        ],
    )
    view_model.search_text = _build_search_text(view_model)
    return view_model


def build_catalogue_snapshot(datasets: list[UnifiedDataset]) -> CatalogueSnapshot:
    dataset_view_models = [dataset_to_view_model(dataset) for dataset in datasets]
    datasets_by_key: dict[tuple[str, str], FrontendDataset] = {}
    distributions_by_key: dict[tuple[str, str], CatalogueDistributionLookup] = {}

    total_distribution_count = 0
    for dataset in dataset_view_models:
        datasets_by_key[(dataset.app, dataset.name)] = dataset
        total_distribution_count += len(dataset.distributions)
        for distribution in dataset.distributions:
            distributions_by_key[(distribution.app, distribution.name)] = (
                CatalogueDistributionLookup(
                    distribution=distribution,
                    dataset=dataset,
                )
            )

    return CatalogueSnapshot(
        datasets=dataset_view_models,
        datasets_by_key=datasets_by_key,
        distributions_by_key=distributions_by_key,
        total_distribution_count=total_distribution_count,
    )


def _build_dcat_rows(
    dto_type: type[Any],
    schema_json: SchemaRegistryPayload,
    values: object,
    *,
    exclude: frozenset[str] = frozenset(),
) -> list[FrontendDcatRow]:
    field_to_term = {_to_snake(info['local_name']): term for term, info in schema_json.items()}
    return [
        (
            field_to_term[field.name],
            schema_json[field_to_term[field.name]]['label'],
            getattr(values, field.name, None),
        )
        for field in dataclasses.fields(dto_type)
        if field.name in field_to_term and field.name not in exclude
    ]


_DATASET_DCAT_ROW_EXCLUDE: frozenset[str] = frozenset({'name', 'description'})


def build_dataset_dcat_rows(
    schema_json: SchemaRegistryPayload,
    dataset: FrontendDataset,
) -> list[FrontendDcatRow]:
    return _build_dcat_rows(UnifiedDataset, schema_json, dataset, exclude=_DATASET_DCAT_ROW_EXCLUDE)


def build_distribution_dcat_rows(
    schema_json: SchemaRegistryPayload,
    distribution: FrontendDistribution,
) -> list[FrontendDcatRow]:
    return _build_dcat_rows(UnifiedDistribution, schema_json, distribution)


def normalise_stat_charts(charts: list[UnifiedStatChart]) -> list[FrontendStatChart]:
    return [
        FrontendStatChart(
            label=chart.label,
            table_name=chart.table_name,
            column_name=chart.column_name,
            chart_type=chart.chart_type,
            data=chart.data,
        )
        for chart in charts
    ]


def _normalise_table_columns(columns: list) -> list[FrontendTableColumn]:
    return [
        FrontendTableColumn(
            name=column.name,
            title=column.title,
            description=column.description,
            datatype=column.datatype,
            property_url=column.property_url,
        )
        for column in columns
    ]


def normalise_tables(tables: list[UnifiedTable]) -> list[FrontendTable]:
    return [
        FrontendTable(
            name=table.name,
            title=table.title,
            description=table.description,
            url=table.url,
            columns=_normalise_table_columns(table.columns),
        )
        for table in tables
    ]


def build_chart_groups(charts: list[FrontendStatChart]) -> list[FrontendStatChartGroup]:
    groups: list[FrontendStatChartGroup] = []
    groups_by_name: dict[str, FrontendStatChartGroup] = {}

    for index, chart in enumerate(charts, start=1):
        rendered_chart = FrontendStatChart(
            label=chart.label,
            table_name=chart.table_name,
            column_name=chart.column_name,
            chart_type=chart.chart_type,
            data=chart.data,
            canvas_idx=index,
        )
        if chart.table_name not in groups_by_name:
            groups_by_name[chart.table_name] = FrontendStatChartGroup(
                table_name=chart.table_name,
                charts=[],
            )
            groups.append(groups_by_name[chart.table_name])
        groups_by_name[chart.table_name].charts.append(rendered_chart)

    return groups


def serialise_stat_charts(charts: list[FrontendStatChart]) -> list[dict[str, object]]:
    return [
        {
            'label': chart.label,
            'table_name': chart.table_name,
            'column_name': chart.column_name,
            'chart_type': chart.chart_type,
            'data': chart.data,
            'canvas_idx': chart.canvas_idx,
        }
        for chart in charts
    ]


def serialise_chart_groups(
    chart_groups: list[FrontendStatChartGroup],
) -> list[dict[str, object]]:
    return [
        {
            'table_name': group.table_name,
            'charts': serialise_stat_charts(group.charts),
        }
        for group in chart_groups
    ]
