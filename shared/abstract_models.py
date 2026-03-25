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
        help_text=_(
            'Contact e-mail address (vcard:hasEmail). '
            'Store as plain email (e.g. user@example.org); exported as mailto: URI on RDF output. '
            'At least one of email or contact_page is required.'
        ),
    )
    contact_page = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Contact Page'),
        help_text=_(
            'URL of a web page that can be used to reach the contact (vcard:hasURL). '
            'Must be a URI/IRI. '
            'At least one of email or contact_page is required.'
        ),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.email or self.contact_page or f'ContactPoint #{self.pk}'

    def clean(self) -> None:
        super().clean()
        if not self.email and not self.contact_page:
            raise ValidationError(
                _(
                    'A contact point must have at least one of email or contact page '
                    '(HealthDCAT-AP v6 vcard:hasEmail / vcard:hasURL).'
                )
            )


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
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Description'),
        help_text=_("dct:description — description of the agent's activities (0..*)"),
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
        blank=False,
        verbose_name=_('Title'),
        help_text=_('dct:title — mandatory per HealthDCAT-AP v6 (1..*)'),
    )
    description = models.TextField(
        null=True,
        blank=False,
        verbose_name=_('Description'),
        help_text=_('dct:description — mandatory per HealthDCAT-AP v6 (1..*)'),
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
            'Legal basis under which this catalog is published — must be a URI/IRI '
            '(mandatory per HealthDCAT-AP v6, e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
        ),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name

    def clean(self) -> None:
        super().clean()
        validate_mandatory_fields(self, ['applicable_legislation', 'title', 'description'])


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
        blank=False,
        verbose_name=_('Title'),
        help_text=_('dct:title — mandatory per HealthDCAT-AP v6 (1..*)'),
    )
    version = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Version'),
    )
    description = models.TextField(
        null=True,
        blank=False,
        verbose_name=_('Description'),
        help_text=_('dct:description — mandatory per HealthDCAT-AP v6 (1..*)'),
    )
    identifier = models.CharField(
        max_length=500,
        verbose_name=_('Identifier'),
        help_text=_(
            'dct:identifier — canonical URI of this dataset from the origin system '
            '(mandatory per HealthDCAT-AP v6, 1..*)'
        ),
    )
    type = models.CharField(
        max_length=500,
        verbose_name=_('Type'),
        help_text=_(
            'dct:type — dataset type URI from EU Dataset-type vocabulary; '
            'comma-separated when multiple, e.g. '
            'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL '
            '(mandatory per HealthDCAT-AP v6, 1..*)'
        ),
    )
    theme = models.CharField(
        max_length=500,
        null=True,
        blank=False,
        verbose_name=_('Theme'),
        help_text=_(
            'dcat:theme — must be a URI/IRI from the EU data-theme vocabulary; '
            'mandatory per HealthDCAT-AP v6 (1..*), '
            'e.g. http://publications.europa.eu/resource/authority/data-theme/HEAL'
        ),
    )
    publisher = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_datasets',
        verbose_name=_('Publisher'),
    )
    conforms_to = models.CharField(
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
        blank=False,
        verbose_name=_('Keywords'),
        help_text=_(
            'dcat:keyword — comma-separated keywords (mandatory per HealthDCAT-AP v6, 1..*)'
        ),
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
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name='datasets',
        verbose_name=_('Contact Point'),
        help_text=_('dcat:contactPoint — mandatory per HealthDCAT-AP v6 (1..*)'),
    )
    provenance = models.TextField(
        null=True,
        blank=False,
        verbose_name=_('Provenance'),
        help_text=_('dct:provenance — mandatory per HealthDCAT-AP v6 (1..*)'),
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
            'dct:accessRights — controlled vocabulary URI (mandatory per HealthDCAT-AP v6)'
        ),
    )
    applicable_legislation = models.CharField(
        max_length=500,
        verbose_name=_('Applicable Legislation'),
        help_text=_(
            'dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
            'e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
        ),
    )
    health_category = models.CharField(
        max_length=500,
        verbose_name=_('Health Category'),
        help_text=_(
            'healthdcat:healthCategory — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
            'e.g. https://healthdataportal.eu/categorisation/Health-care-delivery)'
        ),
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
    custodian = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodian_datasets',
        verbose_name=_('Custodian'),
        help_text=_(
            'geodcatap:custodian — agent responsible for maintaining this dataset '
            '(HealthDCAT-AP Release 6, optional)'
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
            [
                'access_rights',
                'applicable_legislation',
                'health_category',
                'title',
                'description',
                'identifier',
                'type',
                'keyword',
                'theme',
                'provenance',
            ],
        )
        if not self.hdab_id:
            raise ValidationError({'hdab': _('HDAB is mandatory (HealthDCAT-AP v6).')})
        if not self.contact_point_id:
            raise ValidationError(
                {'contact_point': _('contact_point is mandatory (HealthDCAT-AP v6).')}
            )
        # Change 3: HDAB must have a contact point
        if self.hdab_id and self.hdab.contact_point_id is None:
            raise ValidationError(
                {'hdab': _('The HDAB agent must have a contact point (HealthDCAT-AP v6).')}
            )
        # Change 4: publisher, if present, must have a contact point
        if self.publisher_id and self.publisher.contact_point_id is None:
            raise ValidationError(
                {
                    'publisher': _(
                        'The publisher agent must have a contact point (HealthDCAT-AP v6).'
                    )
                }
            )
        # Change 5: custodian, if present, must have a contact point
        if self.custodian_id and self.custodian.contact_point_id is None:
            raise ValidationError(
                {
                    'custodian': _(
                        'The custodian agent must have a contact point (HealthDCAT-AP v6).'
                    )
                }
            )


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
    conforms_to = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Conforms To'),
    )
    byte_size = models.BigIntegerField(
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
        help_text=_(
            'dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
            'e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
        ),
    )
    licence = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_('Licence'),
        help_text=_('dct:license — licence under which this distribution is made available'),
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name

    def clean(self) -> None:
        super().clean()
        validate_mandatory_fields(self, ['access_url', 'applicable_legislation'])
