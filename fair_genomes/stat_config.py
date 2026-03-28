"""
Stat definitions for MOLGENIS FAIR Genomes counts.

``get_stat_definitions()`` is the single place to add, remove, or rename
tracked stats.  The sync machinery reads this function — it never queries the
DB to learn *what* to fetch, only the DB to learn *what to store*.

Each ``StatDef`` describes one count query:

  table        — MOLGENIS table name (same as ``Table.name`` after schema sync),
                 e.g. ``"sequencing"``

  column       — column name within that table (unqualified, no table prefix),
                 e.g. ``"sequencinginstrumentmodel"``

  filter_value — the value to count records by, e.g. ``"MiSeq"``

  column_type  — MOLGENIS GraphQL type string for this column:
                 ``"ref"`` or ``"ref_array"`` → filter wraps the value as
                   ``{column: {value: {equals: "…"}}}``
                 anything else (``"string"``, ``"int"``, …) → filter is
                   ``{column: {equals: "…"}}``
                 Must match the ``datatype`` stored in the Column model after
                 a schema sync.

To add a new stat, append a ``StatDef`` line below.  No DB migration or code
change elsewhere is needed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDef:
    table: str
    column: str
    filter_value: str
    column_type: str


def get_stat_definitions() -> list[StatDef]:
    """Return all stat queries that should be fetched and stored on every sync."""
    return [
        # How many sequencing records used a MiSeq instrument?
        StatDef(
            table='sequencing',
            column='sequencinginstrumentmodel',
            filter_value='MiSeq',
            column_type='ref',
        ),
        # What library preparation kits are used in samplepreparation?
        # Add one StatDef per kit value once the distinct values are known.
        # Example (uncomment and adjust the value):
        # StatDef(
        #     table='samplepreparation',
        #     column='librarypreparationkit',
        #     filter_value='<kit name here>',
        #     column_type='ref',
        # ),
    ]
