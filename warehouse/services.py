"""
Warehouse Metadata Service — encapsulates all direct ORM access for the
warehouse app so that views never touch the database directly.

Every public method returns plain Python data structures (typed payload dicts,
lists, frozensets) rather than Django QuerySets, keeping the view layer fully
decoupled from the ORM.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Mapping

from warehouse.service_types import (
    WarehouseStatChartPayload,
    WarehouseTableColumnPayload,
    WarehouseTablePayload,
    WarehouseTableWithStatsPayload,
)

logger = logging.getLogger(__name__)


class WarehouseMetadataService:
    """Data-access service for warehouse metadata_db and fair_genomes_db queries."""

    # ── Column filter resolution ────────────────────────────────────────────

    def get_dataset_names_by_columns(self, column_titles: set[str]) -> frozenset[str]:
        """Return dataset names whose distributions contain columns matching *column_titles*."""
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

    # ── Sidebar column counts ───────────────────────────────────────────────

    def get_column_counts_for_distributions(self, dist_names: list[str]) -> list[tuple[str, str]]:
        """Return ``(column_title, distribution_name)`` pairs for the given distributions.

        Only non-empty column titles are included.  Results are distinct.
        """
        from warehouse.models import Column

        return list(
            Column.objects.using('metadata_db')
            .filter(table__distribution__in=dist_names)
            .exclude(title='')
            .values_list('title', 'table__distribution_id')
            .distinct()
        )

    # ── Distribution tables + columns ───────────────────────────────────────

    def get_tables_with_columns(
        self,
        distribution_name: str,
    ) -> list[WarehouseTableWithStatsPayload]:
        """Return typed table payloads (with nested column payloads) for a distribution."""
        from warehouse.models import Column, Table

        table_rows = list(
            Table.objects.using('metadata_db')
            .filter(distribution_id=distribution_name)
            .values_list('name', 'title', 'description', 'url')
            .order_by('name')
        )
        table_names = [table_name for table_name, _, _, _ in table_rows]

        col_by_table: defaultdict[str, list[WarehouseTableColumnPayload]] = defaultdict(list)
        for (
            table_name,
            column_name,
            column_title,
            column_description,
            column_datatype,
            property_url,
        ) in (
            Column.objects.using('metadata_db')
            .filter(table_id__in=table_names)
            .values_list('table_id', 'name', 'title', 'description', 'datatype', 'property_url')
            .order_by('table_id', 'var_order', 'name')
        ):
            col_by_table[table_name].append(
                {
                    'name': column_name,
                    'title': column_title,
                    'description': column_description,
                    'datatype': column_datatype,
                    'property_url': property_url,
                }
            )

        return [
            {
                'name': table_name,
                'title': table_title or table_name,
                'description': table_description or '',
                'url': table_url,
                'columns': col_by_table.get(table_name, []),
                'stats': [],
            }
            for table_name, table_title, table_description, table_url in table_rows
        ]

    # ── Tables + columns for multiple distributions (JSON-LD export) ────────

    def get_tables_for_distributions(
        self,
        dist_names: list[str],
    ) -> dict[str, list[WarehouseTablePayload]]:
        """Return typed table payloads for multiple distributions keyed by distribution name."""
        from warehouse.models import Column, Table

        table_rows = list(
            Table.objects.using('metadata_db')
            .filter(distribution_id__in=dist_names)
            .values_list('distribution_id', 'name', 'title', 'description', 'url')
            .order_by('distribution_id', 'name')
        )

        all_table_names = [table_name for _, table_name, _, _, _ in table_rows]
        col_by_table: defaultdict[str, list[WarehouseTableColumnPayload]] = defaultdict(list)
        for (
            table_name,
            column_name,
            column_title,
            column_description,
            column_datatype,
            property_url,
        ) in (
            Column.objects.using('metadata_db')
            .filter(table_id__in=all_table_names)
            .values_list('table_id', 'name', 'title', 'description', 'datatype', 'property_url')
            .order_by('table_id', 'var_order', 'name')
        ):
            col_by_table[table_name].append(
                {
                    'name': column_name,
                    'title': column_title,
                    'description': column_description,
                    'datatype': column_datatype,
                    'property_url': property_url,
                }
            )

        tables_by_dist: defaultdict[str, list[WarehouseTablePayload]] = defaultdict(list)
        for distribution_id, table_name, table_title, table_description, table_url in table_rows:
            tables_by_dist[distribution_id].append(
                {
                    'name': table_name,
                    'title': table_title or table_name,
                    'description': table_description or '',
                    'url': table_url,
                    'columns': col_by_table.get(table_name, []),
                }
            )

        return dict(tables_by_dist)

    # ── Fair Genomes stat charts ────────────────────────────────────────────

    def get_stat_charts(self, distribution_name: str) -> list[WarehouseStatChartPayload]:
        """Return typed stat chart payloads for a Fair Genomes distribution."""
        from fair_genomes.models import StatDefinition as FGStatDefinition
        from fair_genomes.models import StatResult as FGStatResult

        stat_defs = (
            FGStatDefinition.objects.using('fair_genomes_db')
            .filter(distribution__name=distribution_name, is_active=True)
            .order_by('sort_order', 'molgenis_table', 'molgenis_column')
        )
        charts: list[WarehouseStatChartPayload] = []
        for sd in stat_defs:
            sr = (
                FGStatResult.objects.using('fair_genomes_db')
                .filter(table_name=sd.molgenis_table, column_name=sd.molgenis_column)
                .first()
            )
            charts.append(
                {
                    'label': sd.chart_label,
                    'table_name': sd.molgenis_table,
                    'column_name': sd.molgenis_column,
                    'data': (
                        {str(key): int(value) for key, value in sr.distribution.items()}
                        if sr and sr.distribution
                        else {}
                    ),
                }
            )
        return charts

    # ── Derive status (business logic) ──────────────────────────────────────

    @staticmethod
    def derive_status(access_rights: str | None) -> str:
        """
        Derive a simple three-way status from an access-rights URI or label.

        ready       → PUBLIC / open access
        raw         → RESTRICTED / limited / unknown
        unavailable → NON_PUBLIC / closed
        """
        if not access_rights:
            return 'raw'
        ar = access_rights.upper()
        if 'PUBLIC' in ar and 'NON' not in ar:
            return 'ready'
        if 'NON_PUBLIC' in ar or 'NONPUBLIC' in ar or 'CLOSED' in ar:
            return 'unavailable'
        return 'raw'

    # ── Sidebar column counter helper ───────────────────────────────────────

    def build_column_counter(
        self,
        filtered_dist_names: list[str],
        dist_to_dataset: Mapping[str, str],
    ) -> Counter:
        """Build a Counter of column titles across filtered warehouse distributions.

        Each column is counted once per dataset (not per distribution) to avoid
        inflating counts when a dataset has multiple distributions sharing the
        same columns.
        """
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
