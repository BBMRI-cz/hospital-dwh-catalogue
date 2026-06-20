"""FAIR Genomes catalogue read models."""

from __future__ import annotations

from django.db.models import Q

from fair_genomes.models import StatDefinition, StatResult
from shared.dtos import UnifiedStatChart


class FairGenomesCatalogueService:
    """Read FAIR Genomes metadata shaped for catalogue pages."""

    @staticmethod
    def _get_stat_result_map(stat_defs) -> dict[tuple[str, str], dict[str, int]]:
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
            for result in StatResult.objects.using('fair_genomes_db').filter(query)
        }

    def get_stat_charts(self, distribution_name: str) -> list[UnifiedStatChart]:
        stat_defs = list(
            StatDefinition.objects.using('fair_genomes_db')
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
                    chart_type=stat_def.chart_type,
                    data=distributions_by_key.get(stat_key, {}),
                )
            )
        return charts
