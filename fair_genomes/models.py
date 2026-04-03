"""
Fair Genomes Models — HealthDCAT-AP Profile
===========================================

Concrete, managed=True Django models for the FAIR Genomes catalogue.
All models are created and managed by Django migrations in fair_genomes_db.

Design
  All five models (ContactPoint, Agent, Catalog, Dataset, Distribution)
  extend the corresponding shared HealthDCAT-AP abstract base classes from
  shared.abstract_models.  The FAIR Genomes profile requires no schema-specific
  extensions beyond the shared base — it stays intentionally close to the
  HealthDCAT-AP v6 standard.

  If FAIR Genomes-specific fields are needed in the future, add them here
  rather than in the shared base, following the same pattern used by
  warehouse.Distribution.db_layer.

FK strategy
  All FKs point to sibling models in the same app / same DB (fair_genomes_db).
  Cross-DB FKs are never used (enforced by WarehouseRouter).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.abstract_models import (
    AgentBase,
    CatalogBase,
    ContactPointBase,
    DatasetBase,
    DistributionBase,
)


class ContactPoint(ContactPointBase):
    """
    FAIR Genomes ContactPoint.

    Inherits all fields from ContactPointBase (email, contact_page).
    No FAIR Genomes-specific extensions — stays close to the HealthDCAT-AP base.
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_contact_point'
        verbose_name = _('Contact Point')
        verbose_name_plural = _('Contact Points')


class Agent(AgentBase):
    """
    FAIR Genomes Agent (publisher, rights holder, HDAB …).

    Inherits name (PK) and contact_point FK from AgentBase.
    No FAIR Genomes-specific extensions.
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_agent'
        verbose_name = _('Agent')
        verbose_name_plural = _('Agents')


class Catalog(CatalogBase):
    """
    FAIR Genomes Catalog.

    Inherits name (PK), title, description, publisher, applicable_legislation
    from CatalogBase.  No FAIR Genomes-specific extensions.
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_catalog'
        verbose_name = _('Catalog')
        verbose_name_plural = _('Catalogs')


class Dataset(DatasetBase):
    """
    FAIR Genomes Dataset.

    Inherits all shared HealthDCAT-AP fields from DatasetBase including the four
    mandatory HealthDCAT-AP v6 fields:
      access_rights, applicable_legislation, health_category, hdab.

    No FAIR Genomes-specific extensions — this profile intentionally stays close
    to the HealthDCAT-AP v6 standard.  If FAIR Genomes-specific fields are
    needed in the future, add them here (not in the shared base).
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_dataset'
        verbose_name = _('Dataset')
        verbose_name_plural = _('Datasets')
        ordering = ['name']


class Distribution(DistributionBase):
    """
    FAIR Genomes Distribution.

    Inherits all shared HealthDCAT-AP fields from DistributionBase.
    No FAIR Genomes-specific extensions.
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_distribution'
        verbose_name = _('Distribution')
        verbose_name_plural = _('Distributions')


class StatDefinition(models.Model):
    """
    Admin-configurable definition of a single MOLGENIS aggregation query.

    Each row tells the sync machinery to run a ``_groupBy`` GraphQL query on
    ``molgenis_table.molgenis_column`` and display the result on the linked
    Distribution's detail page.

    Replaces the former hardcoded ``stat_config.py``.
    """

    distribution = models.ForeignKey(
        'Distribution',
        on_delete=models.CASCADE,
        related_name='stat_definitions',
        verbose_name=_('Distribution'),
        help_text=_('DCAT Distribution whose detail page should show this chart.'),
    )
    molgenis_table = models.CharField(
        max_length=100,
        verbose_name=_('MOLGENIS table'),
        help_text=_('MOLGENIS table name, e.g. "sequencing"'),
    )
    molgenis_column = models.CharField(
        max_length=200,
        verbose_name=_('MOLGENIS column'),
        help_text=_('Column name within the table, e.g. "sequencinginstrumentmodel"'),
    )
    display_label = models.CharField(
        max_length=300,
        blank=True,
        default='',
        verbose_name=_('Display label'),
        help_text=_('Optional label for the chart. If blank, "table.column" is used.'),
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Sort order'),
        help_text=_('Lower numbers are shown first on the distribution page.'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Inactive definitions are not synced or displayed.'),
    )

    class Meta:
        managed = True
        db_table = 'fair_genomes_stat_definition'
        verbose_name = _('Stat Definition')
        verbose_name_plural = _('Stat Definitions')
        unique_together = [('distribution', 'molgenis_table', 'molgenis_column')]
        ordering = ['distribution', 'sort_order', 'molgenis_table', 'molgenis_column']

    def __str__(self) -> str:
        label = self.display_label or f'{self.molgenis_table}.{self.molgenis_column}'
        return f'{label} → {self.distribution_id}'

    @property
    def chart_label(self) -> str:
        return self.display_label or f'{self.molgenis_table}.{self.molgenis_column}'


class StatResult(models.Model):
    """
    Persisted value distribution for a single (table, column) aggregation.

    ``distribution`` is a JSON object mapping each distinct value to its
    count, e.g. ``{"MiSeq": 87, "NovaSeq": 42, "HiSeq": 15}``.
    """

    table_name = models.CharField(
        max_length=100,
        verbose_name=_('Table name'),
        help_text=_('MOLGENIS table name, e.g. "sequencing"'),
    )
    column_name = models.CharField(
        max_length=200,
        verbose_name=_('Column name'),
        help_text=_('Unqualified column name, e.g. "sequencinginstrumentmodel"'),
    )
    distribution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Distribution'),
        help_text=_('JSON object mapping each distinct value to its record count'),
    )
    last_synced = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last synced'),
    )

    class Meta:
        managed = True
        db_table = 'fair_genomes_stat_result'
        verbose_name = _('Stat Result')
        verbose_name_plural = _('Stat Results')
        unique_together = [('table_name', 'column_name')]
        ordering = ['table_name', 'column_name']

    def __str__(self) -> str:
        n = len(self.distribution) if self.distribution else 0
        return f'{self.table_name}.{self.column_name} ({n} values)'
