"""Read-model queries for warehouse and FAIR Genomes metadata."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from typing import TypeVar

from shared.dtos import (
    ExportColumn,
    ExportTable,
    UnifiedStatChart,
    UnifiedTable,
    UnifiedTableColumn,
)
from shared.normalization import derive_status as derive_catalogue_status

logger = logging.getLogger(__name__)

_ColumnModelT = TypeVar('_ColumnModelT', UnifiedTableColumn, ExportColumn)
_ColumnRow = tuple[str, str, str | None, str | None, str | None, str | None]


class WarehouseMetadataService:
    """Load metadata shaped for the presentation and export layers."""

    def _load_column_rows(self, table_names: list[str]) -> list[_ColumnRow]:
        if not table_names:
            return []

        from warehouse.models import Column

        return list(
            Column.objects.using('metadata_db')
            .filter(table_id__in=table_names)
            .values_list('table_id', 'name', 'title', 'description', 'datatype', 'property_url')
            .order_by('table_id', 'var_order', 'name')
        )

    def _group_columns_by_table(
        self,
        table_names: list[str],
        *,
        build_column: Callable[..., _ColumnModelT],
    ) -> dict[str, list[_ColumnModelT]]:
        columns_by_table: defaultdict[str, list[_ColumnModelT]] = defaultdict(list)
        for (
            table_name,
            column_name,
            column_title,
            column_description,
            column_datatype,
            property_url,
        ) in self._load_column_rows(table_names):
            columns_by_table[table_name].append(
                build_column(
                    name=column_name,
                    title=column_title,
                    description=column_description,
                    datatype=column_datatype,
                    property_url=property_url,
                )
            )
        return dict(columns_by_table)

    def get_dataset_names_by_columns(self, column_titles: set[str]) -> frozenset[str]:
        """Return dataset names whose distributions contain matching columns."""
        from warehouse.models import Column, Distribution

        wh_dist_names = (
            Column.objects.using('metadata_db')
            .filter(title__in=column_titles)
            .values_list('table__distribution_id', flat=True)
            .distinct()
        )
        dataset_names: set[str] = set(
            Distribution.objects.using('metadata_db')
            .filter(name__in=wh_dist_names)
            .values_list('dataset_name', flat=True)
            .distinct()
        )
        return frozenset(dataset_names)

    def get_column_counts_for_distributions(self, dist_names: list[str]) -> list[tuple[str, str]]:
        """Return distinct ``(column_title, distribution_name)`` pairs."""
        from warehouse.models import Column

        return list(
            Column.objects.using('metadata_db')
            .filter(table__distribution__in=dist_names)
            .exclude(title='')
            .values_list('title', 'table__distribution_id')
            .distinct()
        )

    def get_tables_with_columns(
        self,
        distribution_name: str,
    ) -> list[UnifiedTable]:
        """Return table read models for a distribution."""
        from warehouse.models import Table

        table_rows = list(
            Table.objects.using('metadata_db')
            .filter(distribution_id=distribution_name)
            .values_list('name', 'title', 'description', 'url')
            .order_by('name')
        )
        table_names = [table_name for table_name, _, _, _ in table_rows]
        columns_by_table = self._group_columns_by_table(
            table_names,
            build_column=UnifiedTableColumn,
        )

        return [
            UnifiedTable(
                name=table_name,
                title=table_title or table_name,
                description=table_description or '',
                url=table_url,
                columns=[*columns_by_table.get(table_name, ())],
            )
            for table_name, table_title, table_description, table_url in table_rows
        ]

    def get_tables_for_distributions(
        self,
        dist_names: list[str],
    ) -> dict[str, list[ExportTable]]:
        """Return export tables keyed by distribution name."""
        from warehouse.models import Table

        table_rows = list(
            Table.objects.using('metadata_db')
            .filter(distribution_id__in=dist_names)
            .values_list('distribution_id', 'name', 'title', 'description', 'url')
            .order_by('distribution_id', 'name')
        )

        all_table_names = [table_name for _, table_name, _, _, _ in table_rows]
        columns_by_table = self._group_columns_by_table(
            all_table_names,
            build_column=ExportColumn,
        )

        tables_by_dist: defaultdict[str, list[ExportTable]] = defaultdict(list)
        for distribution_id, table_name, table_title, table_description, table_url in table_rows:
            tables_by_dist[distribution_id].append(
                ExportTable(
                    name=table_name,
                    title=table_title,
                    description=table_description,
                    url=table_url,
                    columns=[*columns_by_table.get(table_name, ())],
                )
            )

        return dict(tables_by_dist)

    @staticmethod
    def _get_stat_result_map(stat_defs) -> dict[tuple[str, str], dict[str, int]]:
        from django.db.models import Q

        from fair_genomes.models import StatResult as FGStatResult

        stat_keys = {(stat_def.molgenis_table, stat_def.molgenis_column) for stat_def in stat_defs}
        if not stat_keys:
            return {}

        query = Q()
        for table_name, column_name in stat_keys:
            query |= Q(table_name=table_name, column_name=column_name)

        return {
            (result.table_name, result.column_name): {
                str(key): int(value) for key, value in (result.distribution or {}).items()
            }
            for result in FGStatResult.objects.using('fair_genomes_db').filter(query)
        }

    def get_stat_charts(self, distribution_name: str) -> list[UnifiedStatChart]:
        """Return stat chart read models for a FAIR Genomes distribution."""
        from fair_genomes.models import StatDefinition as FGStatDefinition

        stat_defs = list(
            FGStatDefinition.objects.using('fair_genomes_db')
            .filter(distribution__name=distribution_name, is_active=True)
            .order_by('sort_order', 'molgenis_table', 'molgenis_column')
        )
        distributions_by_key = self._get_stat_result_map(stat_defs)
        charts: list[UnifiedStatChart] = []
        for stat_def in stat_defs:
            stat_key = (stat_def.molgenis_table, stat_def.molgenis_column)
            charts.append(
                UnifiedStatChart(
                    label=stat_def.chart_label,
                    table_name=stat_def.molgenis_table,
                    column_name=stat_def.molgenis_column,
                    data=distributions_by_key.get(stat_key, {}),
                )
            )
        return charts

    @staticmethod
    def derive_status(access_rights: str | None) -> str:
        """Map access-rights data to the catalogue status label."""
        return derive_catalogue_status(access_rights)

    def build_column_counter(
        self,
        filtered_dist_names: list[str],
        dist_to_dataset: Mapping[str, str],
    ) -> Counter:
        """Count columns once per dataset across the filtered distributions."""
        col_counter: Counter = Counter()
        if not filtered_dist_names:
            return col_counter

        seen_col_ds: set[tuple[str, str]] = set()
        attr_rows = self.get_column_counts_for_distributions(filtered_dist_names)
        for title, dist_name in attr_rows:
            ds_name = dist_to_dataset.get(dist_name)
            if ds_name and (title, ds_name) not in seen_col_ds:
                col_counter[title] += 1
                seen_col_ds.add((title, ds_name))

        return col_counter
