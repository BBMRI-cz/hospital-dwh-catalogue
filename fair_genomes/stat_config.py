"""
Stat definitions for MOLGENIS FAIR Genomes aggregations.

``get_stat_definitions()`` is the single place to add, remove, or rename
tracked stats.  The sync machinery reads this function — it never queries the
DB to learn *what* to fetch, only the DB to learn *what to store*.

Each ``StatDef`` describes one aggregation query:

  table              — MOLGENIS table name, e.g. ``"sequencing"``

  column             — column name within that table (unqualified, no table
                       prefix), e.g. ``"sequencinginstrumentmodel"``

  distribution_name  — optional name of the DCAT Distribution whose detail page
                       should display the resulting chart.  When ``None`` the
                       stat is synced and stored but not shown on any page.

The sync fetches a full GROUP BY distribution for each definition, returning
counts of all distinct values in the column.

To add a new stat, append a ``StatDef`` line below.  No DB migration or code
change elsewhere is needed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDef:
    table: str
    column: str
    distribution_name: str | None = None


def get_stat_definitions() -> list[StatDef]:
    """Return all aggregation queries that should be fetched and stored on every sync."""
    return [
        StatDef(
            table='sequencing',
            column='sequencinginstrumentmodel',
            distribution_name='DIST_FG_WES_BAM',
        ),
        StatDef(
            table='sequencing',
            column='librarypreparationkit',
            distribution_name='DIST_FG_WES_BAM',
        ),
        StatDef(
            table='sequencing',
            column='sequencingtype',
            distribution_name='DIST_FG_WES_BAM',
        ),
        StatDef(
            table='sample',
            column='samplematerialtype',
            distribution_name='DIST_FG_WES_BAM',
        ),
        StatDef(
            table='sample',
            column='pathologicalstate',
            distribution_name='DIST_FG_WES_BAM',
        ),
        StatDef(
            table='genomicdata',
            column='genomebuild',
            distribution_name='DIST_FG_WES_BAM',
        ),
    ]


def get_stats_for_distribution(name: str) -> list[StatDef]:
    """Return only the stat definitions linked to a given distribution name."""
    return [sd for sd in get_stat_definitions() if sd.distribution_name == name]
