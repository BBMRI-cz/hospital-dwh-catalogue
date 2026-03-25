"""
Warehouse Models â€” Local Metadata HealthDCAT-AP Profile
=======================================================

Concrete, managed=False Django models for the Local Metadata catalogue.
All models map to pre-existing tables in the metadata_db PostgreSQL schema
(metadata."lm_*") and extend the shared HealthDCAT-AP abstract base models.

Why managed=False?
  The metadata_db schema is maintained externally (DDL migrations are outside
  Django's control).  Django is schema-tracking only; it never creates or
  drops these tables.

Extension points vs the shared base
  * Distribution adds db_layer â€” the physical DWH layer identifier.  This
    concept is absent from FAIR Genomes which has no DWH layer notion.
  * Table/Column are entirely Local Metadata-specific.  Physical table/column metadata
    has no DCAT-AP equivalent; it is added here because the Local Metadata
    schema must describe individual DB table columns.

FK strategy
  All FKs point to sibling models in the same app / same DB.
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
    Local Metadata ContactPoint.

    Inherits all fields from ContactPointBase (email, contact_page).
    No Local Metadata-specific extensions.
    """

    class Meta:
        managed = False
        db_table = 'metadata"."lm_contact_point'
        verbose_name = _('Contact Point')
        verbose_name_plural = _('Contact Points')


class Agent(AgentBase):
    """
    Local Metadata Agent (publisher, rights holder, HDAB â€¦).

    Inherits name (PK) and contact_point FK from AgentBase.
    No Local Metadata-specific extensions.
    """

    class Meta:
        managed = False
        db_table = 'metadata"."lm_agent'
        verbose_name = _('Agent')
        verbose_name_plural = _('Agents')


class Catalog(CatalogBase):
    """
    Local Metadata Catalog.

    Inherits name (PK), title, description, publisher, applicable_legislation
    from CatalogBase.  No Local Metadata-specific extensions.
    """

    class Meta:
        managed = False
        db_table = 'metadata"."lm_catalog'
        verbose_name = _('Catalog')
        verbose_name_plural = _('Catalogs')


class Dataset(DatasetBase):
    """
    Local Metadata Dataset.

    Inherits all shared HealthDCAT-AP fields from DatasetBase including
    the four mandatory HealthDCAT-AP v6 fields:
      access_rights, applicable_legislation, health_category, hdab.

    No Local Metadata-specific extensions at the dataset level; local
    specifics live in Distribution (db_layer), Table (csvw:Table),
    and Column (csvw:Column).
    """

    class Meta:
        managed = False
        db_table = 'metadata"."lm_dataset'
        verbose_name = _('Dataset')
        verbose_name_plural = _('Datasets')
        ordering = ['name']


class Distribution(DistributionBase):
    """
    Local Metadata Distribution.

    Extends DistributionBase with db_layer â€” the physical DWH layer that
    this distribution resides in (e.g. 'raw', 'clean', 'analytical').

    Why db_layer lives here and not in the shared base:
      This is a hospital-DWH-specific concept.  FAIR Genomes catalogues do not
      have DWH layers; adding db_layer to the base would pollute every profile.
    """

    db_layer = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('DB Layer'),
        help_text=_(
            'Physical DWH layer this distribution resides in '
            '(e.g. raw, clean, analytical). Local Metadata-specific field.'
        ),
    )

    class Meta:
        managed = False
        db_table = 'metadata"."lm_distribution'
        verbose_name = _('Distribution')
        verbose_name_plural = _('Distributions')

    def __str__(self) -> str:
        return self.title or self.name


class Table(models.Model):
    """
    Physical DB table metadata for a Distribution (csvw:Table).

    Maps to:  csvw:Table
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('csvw:name — unique identifier for this table'),
    )
    distribution = models.ForeignKey(
        Distribution,
        on_delete=models.CASCADE,
        to_field='name',
        db_column='distribution_name',
        related_name='tables',
        verbose_name=_('Distribution'),
        help_text=_('Distribution this table belongs to'),
    )
    url = models.CharField(
        max_length=500,
        verbose_name=_('URL'),
        help_text=_('csvw:url — physical location / connection string for this table'),
    )
    title = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Title'),
        help_text=_('csvw:title — human-readable table name'),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('dct:description'),
    )

    class Meta:
        managed = False
        db_table = 'metadata"."lm_table'
        verbose_name = _('Table')
        verbose_name_plural = _('Tables')
        ordering = ['name']

    def __str__(self) -> str:
        return self.title or self.name


class Column(models.Model):
    """
    Physical column metadata within a Table (csvw:Column).

    Maps to:  csvw:Column
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('csvw:name — unique column identifier'),
    )
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        to_field='name',
        db_column='table_name',
        related_name='columns',
        verbose_name=_('Table'),
        help_text=_('Table this column belongs to'),
    )
    title = models.CharField(
        max_length=500,
        verbose_name=_('Title'),
        help_text=_('csvw:title — human-readable column name'),
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('dct:description'),
    )
    datatype = models.CharField(
        max_length=100,
        verbose_name=_('Datatype'),
        help_text=_('csvw:datatype — column datatype (e.g. VARCHAR, INTEGER, DATE)'),
    )
    property_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Property URL'),
        help_text=_('csvw:propertyUrl — semantic property URI'),
    )
    var_order = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Variable Order'),
        help_text=_('Position of this column in the source table'),
    )
    key_db = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('DB Key'),
        help_text=_('Primary / foreign key indicator from the DB schema'),
    )
    type_r = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_('R Type'),
        help_text=_('Corresponding R datatype for analytical use'),
    )
    definition_ddl = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('DDL Definition'),
        help_text=_('Full DDL column definition'),
    )
    definition_pk_pom1 = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('PK Definition (helper 1)'),
    )
    definition_pk_pom2 = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('PK Definition (helper 2)'),
    )
    definition_pk = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('PK Definition'),
        help_text=_('Primary key definition expression'),
    )

    class Meta:
        managed = False
        db_table = 'metadata"."lm_column'
        verbose_name = _('Column')
        verbose_name_plural = _('Columns')
        ordering = ['var_order', 'name']

    def __str__(self) -> str:
        return self.title or self.name
