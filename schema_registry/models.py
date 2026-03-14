"""
Schema Registry Models — Health DCAT-AP v6
==========================================

Stores the canonical term definitions and table/column semantic bindings for
a versioned HealthDCAT-AP schema.  All models are managed=True and live in
the `default` database alongside `ticketing` models.

Design rationale
----------------
* SchemaVersion  — one row per spec version (e.g. "v6").  Only one version
                   should be active at a time; the service layer always reads
                   from the active version.
* SchemaPrefix   — prefix→URI mapping per version so a future SHACL/TTL
                   importer can write its own prefix set without touching code.
* SchemaTerm     — one row per unique semantic term.  The `levels` JSONField
                   lists the DCAT-AP levels ("Catalog", "Dataset", …) where
                   the term is applicable, avoiding duplicate rows when the
                   same property appears in multiple tables.
* SchemaFieldBinding — one row per table/column.  Entity rows (is_entity=True)
                       have column_name=None and represent the table-level
                       semantics (e.g. Dataset → dcat:Dataset).

Translation strategy
--------------------
Labels and descriptions are stored in English as `base_label_en` /
`base_description_en`.  Localised text is looked up at runtime via gettext
with stable msgids (schema.term.<term_key>.label / .description); the service
layer falls back to the stored English text when no translation is registered.

Future: SHACL/TTL importer
---------------------------
A future importer will parse a SHACL/TTL file and upsert rows into these
exact same tables.  The service API in services.py must not change — only the
seed source changes.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class SchemaVersion(models.Model):
    """
    A named version of a HealthDCAT-AP schema (e.g. "v6").

    At most one version should have is_active=True at any time.
    The management command seed_schema_v6 sets is_active=True if no active
    version already exists.
    """

    slug = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name=_('Slug'),
        help_text=_('Short machine-readable identifier, e.g. "v6".'),
    )
    label = models.CharField(
        max_length=200,
        verbose_name=_('Label'),
        help_text=_('Human-readable version label, e.g. "Health DCAT-AP v6".'),
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Active'),
        help_text=_('Whether this is the currently active schema version used by the service layer.'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        managed = True
        db_table = 'schema_registry_version'
        ordering = ['-created_at']
        verbose_name = _('Schema Version')
        verbose_name_plural = _('Schema Versions')

    def __str__(self) -> str:
        return f'{self.label} ({"active" if self.is_active else "inactive"})'


class SchemaPrefix(models.Model):
    """
    Namespace prefix → base URI mapping for a given schema version.

    Storing prefixes in the DB (rather than as code constants) allows a future
    SHACL/TTL importer to declare its own prefix set per version without
    requiring a code change.

    Example: prefix="dct", base_uri="http://purl.org/dc/terms/"
    """

    schema_version = models.ForeignKey(
        SchemaVersion,
        on_delete=models.CASCADE,
        related_name='prefixes',
        verbose_name=_('Schema Version'),
    )
    prefix = models.CharField(
        max_length=50,
        verbose_name=_('Prefix'),
        help_text=_('Namespace prefix, e.g. "dct".'),
    )
    base_uri = models.CharField(
        max_length=500,
        verbose_name=_('Base URI'),
        help_text=_('Full namespace URI corresponding to the prefix, e.g. "http://purl.org/dc/terms/".'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        managed = True
        db_table = 'schema_registry_prefix'
        unique_together = [('schema_version', 'prefix')]
        ordering = ['prefix']
        verbose_name = _('Schema Prefix')
        verbose_name_plural = _('Schema Prefixes')

    def __str__(self) -> str:
        return f'{self.prefix}: <{self.base_uri}>'


class SchemaTerm(models.Model):
    """
    A single semantic term within a schema version (e.g. dct:identifier).

    term_key is a stable snake_case identifier used as the gettext msgid base
    and as the stable reference in SchemaFieldBinding.  It must be unique
    within a schema version.

    The `levels` JSONField stores a list of table-level names where this term
    applies (e.g. ["Catalog", "Dataset"]).  This avoids creating duplicate
    SchemaTerm rows when the same DCAT-AP property appears in multiple tables.

    The full URI is derived from prefix+local_name and stored for convenience.
    """

    REQUIREMENT_OPTIONAL = 'optional'
    REQUIREMENT_RECOMMENDED = 'recommended'
    REQUIREMENT_MANDATORY = 'mandatory'
    REQUIREMENT_DEPRECATED = 'deprecated'

    REQUIREMENT_CHOICES = [
        (REQUIREMENT_OPTIONAL, _('Optional')),
        (REQUIREMENT_RECOMMENDED, _('Recommended')),
        (REQUIREMENT_MANDATORY, _('Mandatory')),
        (REQUIREMENT_DEPRECATED, _('Deprecated')),
    ]

    schema_version = models.ForeignKey(
        SchemaVersion,
        on_delete=models.CASCADE,
        related_name='terms',
        verbose_name=_('Schema Version'),
    )
    term_key = models.SlugField(
        max_length=100,
        verbose_name=_('Term Key'),
        help_text=_('Stable snake_case identifier used in gettext msgids and binding references.'),
    )
    semantics = models.CharField(
        max_length=200,
        verbose_name=_('Semantics'),
        help_text=_('Prefixed name, e.g. "dct:identifier".'),
        db_index=True,
    )
    prefix = models.CharField(
        max_length=50,
        verbose_name=_('Prefix'),
        help_text=_('Namespace prefix extracted from semantics for convenience.'),
    )
    local_name = models.CharField(
        max_length=200,
        verbose_name=_('Local Name'),
        help_text=_('Local name extracted from semantics for convenience.'),
    )
    uri = models.CharField(
        max_length=500,
        verbose_name=_('URI'),
        help_text=_('Full URI constructed from prefix base + local_name.'),
    )
    base_label_en = models.CharField(
        max_length=200,
        verbose_name=_('Label (EN)'),
        help_text=_('English base label; used as gettext fallback.'),
    )
    base_description_en = models.TextField(
        verbose_name=_('Description (EN)'),
        help_text=_('English base description; used as gettext fallback.'),
    )
    requirement = models.CharField(
        max_length=20,
        choices=REQUIREMENT_CHOICES,
        default=REQUIREMENT_OPTIONAL,
        verbose_name=_('Requirement'),
        help_text=_('Requirement level per the HealthDCAT-AP specification.'),
    )
    levels = models.JSONField(
        default=list,
        verbose_name=_('Levels'),
        help_text=_('List of table/entity names where this term is applicable, e.g. ["Catalog","Dataset"].'),
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Display Order'),
        help_text=_('Controls the order in which terms are listed within a schema version.'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        managed = True
        db_table = 'schema_registry_term'
        unique_together = [('schema_version', 'term_key')]
        ordering = ['display_order', 'term_key']
        verbose_name = _('Schema Term')
        verbose_name_plural = _('Schema Terms')

    def __str__(self) -> str:
        return f'{self.term_key} ({self.semantics})'


class SchemaFieldBinding(models.Model):
    """
    Binds a schema term to a specific table/column in the data model.

    Entity rows (is_entity=True) represent the table-level semantic mapping
    (e.g. the Dataset table → dcat:Dataset).  For entity rows, column_name
    and column_type are NULL.

    ref_table is populated for FK-like columns to indicate the referenced
    entity (e.g. publisher → Agent).

    label_en / description_en are English strings specific to this binding
    context; they override SchemaTerm.base_label_en where the label differs
    in context (e.g. "name" in Catalog is labelled "Catalogue ID" specifically).
    """

    schema_version = models.ForeignKey(
        SchemaVersion,
        on_delete=models.CASCADE,
        related_name='bindings',
        verbose_name=_('Schema Version'),
    )
    schema_term = models.ForeignKey(
        SchemaTerm,
        on_delete=models.PROTECT,
        related_name='bindings',
        verbose_name=_('Schema Term'),
    )
    table_name = models.CharField(
        max_length=100,
        verbose_name=_('Table Name'),
        help_text=_('Name of the data model table/entity this binding belongs to.'),
    )
    column_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Column Name'),
        help_text=_('Physical column name; NULL for entity (table-level) bindings.'),
    )
    column_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name=_('Column Type'),
        help_text=_('Logical data type (string, text, integer, datetime, ref); NULL for entity rows.'),
    )
    ref_table = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Ref Table'),
        help_text=_('Target entity name for FK-like columns, e.g. "Agent".'),
    )
    label_en = models.CharField(
        max_length=200,
        verbose_name=_('Label (EN)'),
        help_text=_('English label for this binding; may differ from the term label in context.'),
    )
    description_en = models.TextField(
        verbose_name=_('Description (EN)'),
        help_text=_('English description for this binding.'),
    )
    is_entity = models.BooleanField(
        default=False,
        verbose_name=_('Is Entity'),
        help_text=_('True for table-level (entity) rows; False for column-level rows.'),
    )
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Display Order'),
        help_text=_('Controls the order in which bindings are listed within a table.'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        managed = True
        db_table = 'schema_registry_field_binding'
        unique_together = [('schema_version', 'table_name', 'column_name')]
        ordering = ['table_name', 'display_order']
        verbose_name = _('Schema Field Binding')
        verbose_name_plural = _('Schema Field Bindings')

    def __str__(self) -> str:
        col = self.column_name or '(entity)'
        return f'{self.table_name}.{col} → {self.schema_term.semantics}'
