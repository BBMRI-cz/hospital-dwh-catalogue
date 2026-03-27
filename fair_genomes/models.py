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

from django.utils.translation import gettext_lazy as _

from shared.abstract_models import (
    AgentBase,
    CatalogBase,
    ColumnBase,
    ContactPointBase,
    DatasetBase,
    DistributionBase,
    TableBase,
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


class Table(TableBase):
    """
    FAIR Genomes physical table metadata (csvw:Table).

    Inherits name (PK), distribution, url, title, description from TableBase.
    No FAIR Genomes-specific extensions.

    Maps to:  csvw:Table
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_table'
        verbose_name = _('Table')
        verbose_name_plural = _('Tables')
        ordering = ['name']


class Column(ColumnBase):
    """
    FAIR Genomes physical column metadata within a Table (csvw:Column).

    Inherits name (PK), table, title, description, datatype, property_url
    from ColumnBase.  No FAIR Genomes-specific extensions.

    Maps to:  csvw:Column
    """

    class Meta:
        managed = True
        db_table = 'fair_genomes_column'
        verbose_name = _('Column')
        verbose_name_plural = _('Columns')
        ordering = ['name']
