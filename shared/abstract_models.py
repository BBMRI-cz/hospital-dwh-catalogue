"""
Shared HealthDCAT-AP v6 Abstract Base Models
=============================================

These abstract Django models capture all fields and constraints that are
common to every DCAT-AP profile used in this project.

Base vs derived split rationale
--------------------------------
* A field lives HERE when it appears in HealthDCAT-AP v6 and is expected
  on every catalogue profile (Local Metadata, FAIR Genomes, future profiles).
* A field lives in the DERIVED model when it is profile-specific (e.g.
  db_layer is a DWH concept absent from FAIR Genomes; Attribute is a
  physical-column concept with no DCAT-AP equivalent).

Mandatory HealthDCAT-AP v6 fields are enforced via:
  * blank=False on the CharField (rejects empty string at form/serialiser level)
  * clean() delegation to shared.validators.validate_mandatory_fields()

FK strategy
-----------
All FKs inside abstract models reference the concrete sibling model by
string (e.g. 'ContactPoint') so that each derived app resolves relative
to its own label.  Cross-app FK references (e.g. to 'warehouse.Agent')
are NOT used here — that would couple apps and break the multi-DB routing.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.validators import validate_mandatory_fields


class ContactPointBase(models.Model):
    """
    HealthDCAT-AP ContactPoint.

    A means to contact an agent (publisher, rights holder, HDAB …).
    Both fields are optional at the DB level — a ContactPoint may carry
    only an email or only a page URL.

    Maps to:  dcat:contactPoint / vcard:Kind
    """

    email = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Email'),
        help_text=_('Contact e-mail address'),
    )
    contact_page = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Contact Page'),
        help_text=_('URL of a web page that can be used to reach the contact'),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.email or self.contact_page or f'ContactPoint #{self.pk}'


class AgentBase(models.Model):
    """
    HealthDCAT-AP Agent (publisher, creator, rights holder, HDAB …).

    name is used as the natural-key / identifier throughout the catalogue.
    The optional FK to ContactPoint is nullable because agents may be
    referenced before a contact record exists.

    Maps to:  foaf:Agent
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('Unique identifier / name for this agent'),
    )
    # FK resolved at concrete-model level; string reference keeps base portable.
    contact_point = models.ForeignKey(
        'ContactPoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agents',
        verbose_name=_('Contact Point'),
        help_text=_('Contact information for this agent'),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.name


class CatalogBase(models.Model):
    """
    HealthDCAT-AP Catalog — the top-level container for datasets.

    applicable_legislation is mandatory in HealthDCAT-AP v6 (e.g. the EU
    health data space regulation reference).

    Maps to:  dcat:Catalog
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('Unique identifier for this catalog'),
    )
    title = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Title'),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
    )
    # Nullable FK: a catalog can temporarily lack a publisher record.
    publisher = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='catalogs',
        verbose_name=_('Publisher'),
        help_text=_('Agent responsible for making this catalog available'),
    )
    # MANDATORY — HealthDCAT-AP v6 §4.2
    applicable_legislation = models.CharField(
        max_length=500,
        verbose_name=_('Applicable Legislation'),
        help_text=_(
            'Legal basis under which this catalog is published '
            '(mandatory per HealthDCAT-AP v6)'
        ),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name

    def clean(self) -> None:
        super().clean()
        validate_mandatory_fields(self, ['applicable_legislation'])


class DatasetBase(models.Model):
    """
    HealthDCAT-AP Dataset.

    Mandatory HealthDCAT-AP v6 fields (blank=False + validated in clean()):
      * access_rights         — dct:accessRights
      * applicable_legislation — dct:applicableLegislation
      * health_category       — healthdcat:healthCategory
      * hdab                  — healthdcat:hdab (FK to Agent)

    All other fields are optional at the DB level; fill-rate rules may
    be enforced at the application / serialiser layer.

    Maps to:  dcat:Dataset
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('Unique identifier for this dataset'),
    )
    title = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Title'),
    )
    version = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Version'),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
    )
    theme = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Theme'),
        help_text=_('dcat:theme — category from a controlled vocabulary'),
    )
    publisher = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_datasets',
        verbose_name=_('Publisher'),
    )
    license = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('License'),
        help_text=_('dct:license — URL or SPDX identifier'),
    )
    conformed_to = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Conforms To'),
        help_text=_('dct:conformsTo — standard / specification URI'),
    )
    issued = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Issued'),
        help_text=_('dct:issued — date of first publication'),
    )
    modified = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Modified'),
        help_text=_('dct:modified — date of last modification'),
    )
    keyword = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Keywords'),
        help_text=_('dcat:keyword — comma-separated keywords'),
    )
    source = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Source'),
        help_text=_('dct:source — URI of the source dataset'),
    )
    creator = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Creator'),
        help_text=_('dct:creator — name(s) of the dataset creator(s)'),
    )
    contact_point = models.ForeignKey(
        'ContactPoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datasets',
        verbose_name=_('Contact Point'),
    )
    rights_holder = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Rights Holder'),
        help_text=_('dct:rightsHolder'),
    )
    provenance = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Provenance'),
        help_text=_('dct:provenance'),
    )
    catalog = models.ForeignKey(
        'Catalog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datasets',
        verbose_name=_('Catalog'),
    )

    # ── Mandatory HealthDCAT-AP v6 fields ──────────────────────────────────
    # blank=False prevents empty strings; clean() checks non-null FKs too.

    access_rights = models.CharField(
        max_length=500,
        verbose_name=_('Access Rights'),
        help_text=_(
            'dct:accessRights — controlled vocabulary URI '
            '(mandatory per HealthDCAT-AP v6)'
        ),
    )
    applicable_legislation = models.CharField(
        max_length=500,
        verbose_name=_('Applicable Legislation'),
        help_text=_('dct:applicableLegislation (mandatory per HealthDCAT-AP v6)'),
    )
    health_category = models.CharField(
        max_length=500,
        verbose_name=_('Health Category'),
        help_text=_('healthdcat:healthCategory (mandatory per HealthDCAT-AP v6)'),
    )
    hdab = models.ForeignKey(
        'Agent',
        on_delete=models.PROTECT,
        related_name='hdab_datasets',
        verbose_name=_('HDAB'),
        help_text=_(
            'healthdcat:hdab — Health Data Access Body responsible for '
            'this dataset (mandatory per HealthDCAT-AP v6)'
        ),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name

    def clean(self) -> None:
        super().clean()
        validate_mandatory_fields(
            self,
            ['access_rights', 'applicable_legislation', 'health_category'],
        )
        if not self.hdab_id:
            raise ValidationError({'hdab': _('HDAB is mandatory (HealthDCAT-AP v6).')})


class DistributionBase(models.Model):
    """
    HealthDCAT-AP Distribution — a specific representation of a dataset.

    Mandatory HealthDCAT-AP v6 fields:
      * access_url            — dcat:accessURL
      * applicable_legislation — dct:applicableLegislation

    dataset_name is a FK to Dataset.name (the natural key) rather than
    the auto-increment PK, so that the identifier stays human-readable
    in serialised output (CSV, RDF, REST).

    Maps to:  dcat:Distribution
    """

    name = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_('Name'),
        help_text=_('Unique identifier for this distribution'),
    )
    dataset_name = models.ForeignKey(
        'Dataset',
        on_delete=models.CASCADE,
        to_field='name',
        db_column='dataset_name',
        related_name='distributions',
        verbose_name=_('Dataset'),
        help_text=_('Dataset this distribution belongs to'),
    )
    title = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Title'),
    )
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
    )
    format = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Format'),
        help_text=_('dct:format — media type or format URI'),
    )
    conformed_to = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Conforms To'),
    )
    byte_size = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Byte Size'),
        help_text=_('dcat:byteSize'),
    )
    rights = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Rights'),
        help_text=_('dct:rights'),
    )
    issued = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Issued'),
    )
    modified = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Modified'),
    )

    # ── Mandatory HealthDCAT-AP v6 fields ──────────────────────────────────

    access_url = models.CharField(
        max_length=500,
        verbose_name=_('Access URL'),
        help_text=_('dcat:accessURL (mandatory per HealthDCAT-AP v6)'),
    )
    applicable_legislation = models.CharField(
        max_length=500,
        verbose_name=_('Applicable Legislation'),
        help_text=_('dct:applicableLegislation (mandatory per HealthDCAT-AP v6)'),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name

    def clean(self) -> None:
        super().clean()
        validate_mandatory_fields(self, ['access_url', 'applicable_legislation'])
