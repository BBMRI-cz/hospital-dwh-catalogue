"""
Health DCAT-AP v6 — Hardcoded Seed Definitions
===============================================

This module is the ONLY place that knows about the v6 spec content.
Everything else (management command, service layer) is spec-agnostic.

Future: SHACL / TTL importer
-----------------------------
When a SHACL/TTL importer is implemented, replace this module (or add a
parallel loader) that parses the TTL and returns data in the same shape
as TERMS and BINDINGS below.  The management command and service layer
must NOT change — only the seed source changes.

# TODO(future): implement import_from_shacl(ttl_path) that returns
#   (PREFIX_MAP, TERMS, BINDINGS) in the same format as defined below,
#   then call it from seed_schema_v6.py instead of importing this module.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Namespace prefix → base URI
# Note: dct and dcterms both resolve to the same Dublin Core Terms namespace.
# Both are kept because the spec uses them interchangeably; the management
# command normalises semantics to a single canonical form when building URIs.
# ---------------------------------------------------------------------------
PREFIX_MAP: dict[str, str] = {
    'foaf':         'http://xmlns.com/foaf/0.1/',
    'dcat':         'http://www.w3.org/ns/dcat#',
    'dct':          'http://purl.org/dc/terms/',
    'dcterms':      'http://purl.org/dc/terms/',
    'csvw':         'http://www.w3.org/ns/csvw#',
    'vcard':        'http://www.w3.org/2006/vcard/ns#',
    'cv':           'http://data.europa.eu/m8g/',
    'dcatap':       'http://data.europa.eu/r5r/',
    'healthdcatap': 'https://healthdataportal.eu/ns/health-dcat-ap#',
    'fdp-o':        'https://w3id.org/fdp/fdp-o#',
    # Internal prefix for physical FK columns that have no DCAT-AP counterpart.
    'local':        'urn:local:schema-registry:',
}

# ---------------------------------------------------------------------------
# Schema version metadata
# ---------------------------------------------------------------------------
VERSION_SLUG = 'v6'
VERSION_LABEL = 'Health DCAT-AP v6'

# ---------------------------------------------------------------------------
# Term definitions
#
# term_key: stable snake_case identifier — do NOT rename after initial seed.
# semantics: prefixed name as it appears in the spec.
# levels: list of table/entity names where this term is applicable.
# requirement: 'optional' | 'recommended' | 'mandatory' | 'deprecated'
# display_order: controls listing order, grouped by conceptual cluster.
# ---------------------------------------------------------------------------
TERMS: list[dict] = [
    # ── Agent ───────────────────────────────────────────────────────────────
    {
        'term_key': 'agent_entity',
        'semantics': 'foaf:Agent',
        'base_label_en': 'Agent',
        'base_description_en': 'An entity (person, group, or organisation) that can act or be held responsible for actions relating to data.',
        'requirement': 'mandatory',
        'levels': ['Agent'],
        'display_order': 10,
    },
    {
        'term_key': 'foaf_name',
        'semantics': 'foaf:name',
        'base_label_en': 'Name',
        'base_description_en': 'A human-readable name identifying the agent, used as the primary key in this data model.',
        'requirement': 'mandatory',
        'levels': ['Agent'],
        'display_order': 11,
    },
    # ── ContactPoint ─────────────────────────────────────────────────────────
    {
        'term_key': 'contact_point_entity',
        'semantics': 'vcard:Kind',
        'base_label_en': 'Contact Point',
        'base_description_en': 'A vCard-based contact entity providing means to reach an agent or data owner.',
        'requirement': 'optional',
        'levels': ['ContactPoint'],
        'display_order': 20,
    },
    {
        'term_key': 'has_email',
        'semantics': 'vcard:hasEmail',
        'base_label_en': 'Email',
        'base_description_en': 'An e-mail address through which the contact point can be reached.',
        'requirement': 'optional',
        'levels': ['ContactPoint'],
        'display_order': 21,
    },
    {
        'term_key': 'has_url',
        'semantics': 'vcard:hasURL',
        'base_label_en': 'Contact Page',
        'base_description_en': 'A URL of a web page that can be used to contact or learn more about the contact point.',
        'requirement': 'optional',
        'levels': ['ContactPoint'],
        'display_order': 22,
    },
    {
        'term_key': 'cv_contact_point',
        'semantics': 'cv:contactPoint',
        'base_label_en': 'Contact Point',
        'base_description_en': 'Links an agent to a contact point that provides means for reaching them.',
        'requirement': 'optional',
        'levels': ['Agent'],
        'display_order': 23,
    },
    # ── Catalog ──────────────────────────────────────────────────────────────
    {
        'term_key': 'catalog_entity',
        'semantics': 'dcat:Catalog',
        'base_label_en': 'Catalog',
        'base_description_en': 'A curated collection of metadata describing datasets and data services.',
        'requirement': 'mandatory',
        'levels': ['Catalog'],
        'display_order': 30,
    },
    # ── Shared: identifier, title, description ────────────────────────────
    {
        'term_key': 'identifier',
        'semantics': 'dct:identifier',
        'base_label_en': 'Identifier',
        'base_description_en': 'A unique identifier for the resource within its containing catalogue or system.',
        'requirement': 'mandatory',
        'levels': ['Catalog', 'Dataset', 'Distribution', 'Attribute'],
        'display_order': 40,
    },
    {
        'term_key': 'title',
        'semantics': 'dct:title',
        'base_label_en': 'Title',
        'base_description_en': 'A human-readable name or heading given to the resource.',
        'requirement': 'mandatory',
        'levels': ['Catalog', 'Dataset', 'Distribution', 'Attribute'],
        'display_order': 41,
    },
    {
        'term_key': 'description',
        'semantics': 'dct:description',
        'base_label_en': 'Description',
        'base_description_en': 'A free-text account of the resource explaining its content, scope, or purpose.',
        'requirement': 'recommended',
        'levels': ['Catalog', 'Dataset', 'Distribution', 'Attribute'],
        'display_order': 42,
    },
    {
        'term_key': 'publisher',
        'semantics': 'dct:publisher',
        'base_label_en': 'Publisher',
        'base_description_en': 'The agent (person or organisation) responsible for making the resource available.',
        'requirement': 'mandatory',
        'levels': ['Catalog', 'Dataset'],
        'display_order': 43,
    },
    {
        'term_key': 'applicable_legislation',
        'semantics': 'dcatap:applicableLegislation',
        'base_label_en': 'Applicable Legislation',
        'base_description_en': 'A legal provision or regulation that mandates the creation or management of this resource.',
        'requirement': 'recommended',
        'levels': ['Catalog', 'Dataset', 'Distribution'],
        'display_order': 44,
    },
    # ── Dataset-specific ─────────────────────────────────────────────────────
    {
        'term_key': 'dataset_entity',
        'semantics': 'dcat:Dataset',
        'base_label_en': 'Dataset',
        'base_description_en': 'A collection of data published or curated by a single agent and available for access or download.',
        'requirement': 'mandatory',
        'levels': ['Dataset'],
        'display_order': 50,
    },
    {
        'term_key': 'has_version',
        'semantics': 'dcterms:hasVersion',
        'base_label_en': 'Version',
        'base_description_en': 'A version label or number identifying a specific release or iteration of the dataset.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 51,
    },
    {
        'term_key': 'theme',
        'semantics': 'dcat:theme',
        'base_label_en': 'Theme',
        'base_description_en': 'A subject category from a controlled vocabulary (e.g. EuroVoc) that describes the dataset topic.',
        'requirement': 'recommended',
        'levels': ['Dataset'],
        'display_order': 52,
    },
    {
        'term_key': 'license',
        'semantics': 'dct:license',
        'base_label_en': 'License',
        'base_description_en': 'A legal document or URI giving official permission to access, use, or redistribute the resource.',
        'requirement': 'recommended',
        'levels': ['Dataset'],
        'display_order': 53,
    },
    {
        'term_key': 'conforms_to',
        'semantics': 'dct:conformsTo',
        'base_label_en': 'Conforms To',
        'base_description_en': 'A standard, specification, or schema that the resource conforms to.',
        'requirement': 'optional',
        'levels': ['Dataset', 'Distribution'],
        'display_order': 54,
    },
    {
        'term_key': 'metadata_issued',
        'semantics': 'fdp-o:metadataIssued',
        'base_label_en': 'Metadata Issued',
        'base_description_en': 'The date and time when the metadata record for this dataset was first published.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 55,
    },
    {
        'term_key': 'metadata_modified',
        'semantics': 'fdp-o:metadataModified',
        'base_label_en': 'Metadata Modified',
        'base_description_en': 'The date and time when the metadata record for this dataset was last changed.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 56,
    },
    {
        'term_key': 'keyword',
        'semantics': 'dcat:keyword',
        'base_label_en': 'Keywords',
        'base_description_en': 'A comma- or space-separated list of keywords or tags describing the dataset.',
        'requirement': 'recommended',
        'levels': ['Dataset'],
        'display_order': 57,
    },
    {
        'term_key': 'source',
        'semantics': 'dct:source',
        'base_label_en': 'Source',
        'base_description_en': 'A related resource from which the described dataset is derived.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 58,
    },
    {
        'term_key': 'creator',
        'semantics': 'dct:creator',
        'base_label_en': 'Creator',
        'base_description_en': 'An entity primarily responsible for making the dataset.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 59,
    },
    {
        'term_key': 'contact_point',
        'semantics': 'dcat:contactPoint',
        'base_label_en': 'Contact Point',
        'base_description_en': 'Contact information for enquiries about this resource.',
        'requirement': 'recommended',
        'levels': ['Dataset'],
        'display_order': 60,
    },
    {
        'term_key': 'rights_holder',
        'semantics': 'dct:rightsHolder',
        'base_label_en': 'Rights Holder',
        'base_description_en': 'An entity that holds, administers, or manages rights over the dataset.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 61,
    },
    {
        'term_key': 'provenance',
        'semantics': 'dct:provenance',
        'base_label_en': 'Provenance',
        'base_description_en': 'A statement of any changes in ownership, custody, or collection process that are significant for its authenticity.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 62,
    },
    {
        'term_key': 'access_rights',
        'semantics': 'dct:accessRights',
        'base_label_en': 'Access Rights',
        'base_description_en': 'Information about who can access the resource and under what conditions.',
        'requirement': 'recommended',
        'levels': ['Dataset'],
        'display_order': 63,
    },
    {
        'term_key': 'health_category',
        'semantics': 'healthdcatap:healthCategory',
        'base_label_en': 'Health Category',
        'base_description_en': 'A health-domain category from a controlled vocabulary that classifies the type of health data in the dataset.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 64,
    },
    {
        'term_key': 'health_data_access_body',
        'semantics': 'healthdcatap:healthDataAccessBody',
        'base_label_en': 'Health Data Access Body',
        'base_description_en': 'The body or authority responsible for granting access to the health dataset under applicable legislation.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 65,
    },
    {
        'term_key': 'in_catalog',
        'semantics': 'dcat:inCatalog',
        'base_label_en': 'Catalogue',
        'base_description_en': 'The catalogue in which this dataset is published.',
        'requirement': 'optional',
        'levels': ['Dataset'],
        'display_order': 66,
    },
    # ── Distribution-specific ─────────────────────────────────────────────────
    {
        'term_key': 'distribution_entity',
        'semantics': 'csvw:Table',
        'base_label_en': 'Distribution',
        'base_description_en': 'A specific representation of a dataset, modelled as a tabular resource (csvw:Table).',
        'requirement': 'optional',
        'levels': ['Distribution'],
        'display_order': 70,
    },
    {
        'term_key': 'format',
        'semantics': 'dct:format',
        'base_label_en': 'Format',
        'base_description_en': 'The file format, physical medium, or dimensions of the resource.',
        'requirement': 'optional',
        'levels': ['Distribution'],
        'display_order': 71,
    },
    {
        'term_key': 'access_url',
        'semantics': 'dcat:accessURL',
        'base_label_en': 'Access URL',
        'base_description_en': 'A URL that gives access to the distribution of the dataset.',
        'requirement': 'recommended',
        'levels': ['Distribution'],
        'display_order': 72,
    },
    {
        'term_key': 'byte_size',
        'semantics': 'dcat:byteSize',
        'base_label_en': 'Byte Size',
        'base_description_en': 'The size of the distribution in bytes.',
        'requirement': 'optional',
        'levels': ['Distribution'],
        'display_order': 73,
    },
    {
        'term_key': 'rights',
        'semantics': 'dct:rights',
        'base_label_en': 'Rights',
        'base_description_en': 'A statement about rights associated with the distribution.',
        'requirement': 'optional',
        'levels': ['Distribution'],
        'display_order': 74,
    },
    {
        'term_key': 'distribution_dataset_fk',
        'semantics': 'local:datasetFK',
        'base_label_en': 'Dataset Reference',
        'base_description_en': 'Physical FK column linking the distribution to its parent dataset by identifier.',
        'requirement': 'mandatory',
        'levels': ['Distribution'],
        'display_order': 75,
    },
    # ── Attribute (Column) ─────────────────────────────────────────────────────
    {
        'term_key': 'attribute_entity',
        'semantics': 'csvw:Column',
        'base_label_en': 'Table Column',
        'base_description_en': 'A column definition within a tabular distribution, described using the CSVW vocabulary.',
        'requirement': 'optional',
        'levels': ['Attribute'],
        'display_order': 80,
    },
    {
        'term_key': 'attribute_distribution_fk',
        'semantics': 'local:distributionFK',
        'base_label_en': 'Distribution Reference',
        'base_description_en': 'Physical FK column linking the attribute to its parent distribution by identifier.',
        'requirement': 'mandatory',
        'levels': ['Attribute'],
        'display_order': 81,
    },
    {
        'term_key': 'csvw_name',
        'semantics': 'csvw:name',
        'base_label_en': 'Column ID',
        'base_description_en': 'The machine-readable identifier of the column within the distribution.',
        'requirement': 'mandatory',
        'levels': ['Attribute'],
        'display_order': 82,
    },
    {
        'term_key': 'csvw_title',
        'semantics': 'csvw:title',
        'base_label_en': 'Column Name',
        'base_description_en': 'A human-readable title for the column as displayed in interfaces or documentation.',
        'requirement': 'recommended',
        'levels': ['Attribute'],
        'display_order': 83,
    },
    {
        'term_key': 'csvw_datatype',
        'semantics': 'csvw:datatype',
        'base_label_en': 'Column Datatype',
        'base_description_en': 'The data type of the values in this column, e.g. string, integer, date.',
        'requirement': 'optional',
        'levels': ['Attribute'],
        'display_order': 84,
    },
    {
        'term_key': 'csvw_property_url',
        'semantics': 'csvw:propertyURL',
        'base_label_en': 'Property URL',
        'base_description_en': 'A URL identifying the RDF property that corresponds to values in this column.',
        'requirement': 'optional',
        'levels': ['Attribute'],
        'display_order': 85,
    },
]

# ---------------------------------------------------------------------------
# Field binding definitions
#
# table_name: entity/table name exactly as used in the data model.
# column_name: None for entity rows (is_entity=True).
# column_type: None for entity rows; one of string/text/integer/datetime/ref.
# ref_table: target entity name for ref-type columns; None otherwise.
# term_key: must match a term_key in TERMS above.
# is_entity: True only for the table-level (entity) binding row.
# display_order: controls ordering within the table.
# ---------------------------------------------------------------------------
BINDINGS: list[dict] = [
    # ── Agent ────────────────────────────────────────────────────────────────
    {
        'table_name': 'Agent', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'agent_entity', 'is_entity': True,
        'label_en': 'Agent',
        'description_en': 'An entity that can act or be held responsible for data-related actions.',
        'display_order': 0,
    },
    {
        'table_name': 'Agent', 'column_name': 'name', 'column_type': 'string',
        'ref_table': None, 'term_key': 'foaf_name', 'is_entity': False,
        'label_en': 'Name',
        'description_en': 'Human-readable name identifying the agent; used as the primary business key.',
        'display_order': 1,
    },
    {
        'table_name': 'Agent', 'column_name': 'contactPoint', 'column_type': 'ref',
        'ref_table': 'ContactPoint', 'term_key': 'cv_contact_point', 'is_entity': False,
        'label_en': 'Contact Point',
        'description_en': 'A contact point providing means to reach this agent.',
        'display_order': 2,
    },
    # ── ContactPoint ─────────────────────────────────────────────────────────
    {
        'table_name': 'ContactPoint', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'contact_point_entity', 'is_entity': True,
        'label_en': 'Contact Point',
        'description_en': 'A vCard-based contact entity providing ways to reach an agent.',
        'display_order': 0,
    },
    {
        'table_name': 'ContactPoint', 'column_name': 'email', 'column_type': 'string',
        'ref_table': None, 'term_key': 'has_email', 'is_entity': False,
        'label_en': 'Email',
        'description_en': 'E-mail address of the contact point.',
        'display_order': 1,
    },
    {
        'table_name': 'ContactPoint', 'column_name': 'contactPage', 'column_type': 'string',
        'ref_table': None, 'term_key': 'has_url', 'is_entity': False,
        'label_en': 'Contact Page',
        'description_en': 'URL of a web page through which the contact can be reached.',
        'display_order': 2,
    },
    # ── Catalog ──────────────────────────────────────────────────────────────
    {
        'table_name': 'Catalog', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'catalog_entity', 'is_entity': True,
        'label_en': 'Catalog',
        'description_en': 'A curated collection of metadata about datasets and data services.',
        'display_order': 0,
    },
    {
        'table_name': 'Catalog', 'column_name': 'name', 'column_type': 'string',
        'ref_table': None, 'term_key': 'identifier', 'is_entity': False,
        'label_en': 'Catalogue ID',
        'description_en': 'A unique identifier for the catalogue within the system.',
        'display_order': 1,
    },
    {
        'table_name': 'Catalog', 'column_name': 'title', 'column_type': 'string',
        'ref_table': None, 'term_key': 'title', 'is_entity': False,
        'label_en': 'Title',
        'description_en': 'Human-readable name of the catalogue.',
        'display_order': 2,
    },
    {
        'table_name': 'Catalog', 'column_name': 'description', 'column_type': 'text',
        'ref_table': None, 'term_key': 'description', 'is_entity': False,
        'label_en': 'Description',
        'description_en': 'A free-text description of the catalogue scope and content.',
        'display_order': 3,
    },
    {
        'table_name': 'Catalog', 'column_name': 'publisher', 'column_type': 'ref',
        'ref_table': 'Agent', 'term_key': 'publisher', 'is_entity': False,
        'label_en': 'Publisher',
        'description_en': 'The organisation or person responsible for publishing the catalogue.',
        'display_order': 4,
    },
    {
        'table_name': 'Catalog', 'column_name': 'applicableLegislation', 'column_type': 'string',
        'ref_table': None, 'term_key': 'applicable_legislation', 'is_entity': False,
        'label_en': 'Applicable Legislation',
        'description_en': 'The legal act or regulation under which the catalogue is established.',
        'display_order': 5,
    },
    # ── Dataset ───────────────────────────────────────────────────────────────
    {
        'table_name': 'Dataset', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'dataset_entity', 'is_entity': True,
        'label_en': 'Dataset',
        'description_en': 'A collection of data published by an organisation and available for access.',
        'display_order': 0,
    },
    {
        'table_name': 'Dataset', 'column_name': 'name', 'column_type': 'string',
        'ref_table': None, 'term_key': 'identifier', 'is_entity': False,
        'label_en': 'Dataset ID',
        'description_en': 'A unique identifier for the dataset within the catalogue.',
        'display_order': 1,
    },
    {
        'table_name': 'Dataset', 'column_name': 'title', 'column_type': 'string',
        'ref_table': None, 'term_key': 'title', 'is_entity': False,
        'label_en': 'Title',
        'description_en': 'Human-readable name of the dataset.',
        'display_order': 2,
    },
    {
        'table_name': 'Dataset', 'column_name': 'version', 'column_type': 'string',
        'ref_table': None, 'term_key': 'has_version', 'is_entity': False,
        'label_en': 'Version',
        'description_en': 'Version label or number of this dataset release.',
        'display_order': 3,
    },
    {
        'table_name': 'Dataset', 'column_name': 'description', 'column_type': 'text',
        'ref_table': None, 'term_key': 'description', 'is_entity': False,
        'label_en': 'Description',
        'description_en': 'A free-text description explaining the content and scope of the dataset.',
        'display_order': 4,
    },
    {
        'table_name': 'Dataset', 'column_name': 'theme', 'column_type': 'string',
        'ref_table': None, 'term_key': 'theme', 'is_entity': False,
        'label_en': 'Theme',
        'description_en': 'A subject category classifying the topic area of the dataset.',
        'display_order': 5,
    },
    {
        'table_name': 'Dataset', 'column_name': 'publisher', 'column_type': 'ref',
        'ref_table': 'Agent', 'term_key': 'publisher', 'is_entity': False,
        'label_en': 'Publisher',
        'description_en': 'The organisation or person responsible for publishing the dataset.',
        'display_order': 6,
    },
    {
        'table_name': 'Dataset', 'column_name': 'license', 'column_type': 'string',
        'ref_table': None, 'term_key': 'license', 'is_entity': False,
        'label_en': 'License',
        'description_en': 'A URI or identifier of the license governing use of this dataset.',
        'display_order': 7,
    },
    {
        'table_name': 'Dataset', 'column_name': 'conformedTo', 'column_type': 'string',
        'ref_table': None, 'term_key': 'conforms_to', 'is_entity': False,
        'label_en': 'Conforms To',
        'description_en': 'A standard, specification, or schema that this dataset conforms to.',
        'display_order': 8,
    },
    {
        'table_name': 'Dataset', 'column_name': 'issued', 'column_type': 'datetime',
        'ref_table': None, 'term_key': 'metadata_issued', 'is_entity': False,
        'label_en': 'Metadata Issued',
        'description_en': 'Timestamp when the metadata record for this dataset was first published.',
        'display_order': 9,
    },
    {
        'table_name': 'Dataset', 'column_name': 'modified', 'column_type': 'datetime',
        'ref_table': None, 'term_key': 'metadata_modified', 'is_entity': False,
        'label_en': 'Metadata Modified',
        'description_en': 'Timestamp when the metadata record for this dataset was last updated.',
        'display_order': 10,
    },
    {
        'table_name': 'Dataset', 'column_name': 'keyword', 'column_type': 'text',
        'ref_table': None, 'term_key': 'keyword', 'is_entity': False,
        'label_en': 'Keywords',
        'description_en': 'Keywords or tags describing the subject matter of the dataset.',
        'display_order': 11,
    },
    {
        'table_name': 'Dataset', 'column_name': 'source', 'column_type': 'text',
        'ref_table': None, 'term_key': 'source', 'is_entity': False,
        'label_en': 'Source',
        'description_en': 'A related resource from which this dataset is derived or sourced.',
        'display_order': 12,
    },
    {
        'table_name': 'Dataset', 'column_name': 'creator', 'column_type': 'text',
        'ref_table': None, 'term_key': 'creator', 'is_entity': False,
        'label_en': 'Creator',
        'description_en': 'The entity primarily responsible for creating the dataset.',
        'display_order': 13,
    },
    {
        'table_name': 'Dataset', 'column_name': 'contactPoint', 'column_type': 'ref',
        'ref_table': 'ContactPoint', 'term_key': 'contact_point', 'is_entity': False,
        'label_en': 'Contact Point',
        'description_en': 'Contact information for enquiries about this dataset.',
        'display_order': 14,
    },
    {
        'table_name': 'Dataset', 'column_name': 'rightsHolder', 'column_type': 'text',
        'ref_table': None, 'term_key': 'rights_holder', 'is_entity': False,
        'label_en': 'Rights Holder',
        'description_en': 'The entity that holds or administers rights over this dataset.',
        'display_order': 15,
    },
    {
        'table_name': 'Dataset', 'column_name': 'provenance', 'column_type': 'text',
        'ref_table': None, 'term_key': 'provenance', 'is_entity': False,
        'label_en': 'Provenance',
        'description_en': 'A statement describing the origin, custody, or collection process of the dataset.',
        'display_order': 16,
    },
    {
        'table_name': 'Dataset', 'column_name': 'accessRights', 'column_type': 'string',
        'ref_table': None, 'term_key': 'access_rights', 'is_entity': False,
        'label_en': 'Access Rights',
        'description_en': 'Information about who may access the dataset and under what conditions.',
        'display_order': 17,
    },
    {
        'table_name': 'Dataset', 'column_name': 'applicableLegislation', 'column_type': 'string',
        'ref_table': None, 'term_key': 'applicable_legislation', 'is_entity': False,
        'label_en': 'Applicable Legislation',
        'description_en': 'The legal act or regulation applicable to this dataset.',
        'display_order': 18,
    },
    {
        'table_name': 'Dataset', 'column_name': 'healthCategory', 'column_type': 'string',
        'ref_table': None, 'term_key': 'health_category', 'is_entity': False,
        'label_en': 'Health Category',
        'description_en': 'A health-domain category from a controlled vocabulary classifying the type of health data.',
        'display_order': 19,
    },
    {
        'table_name': 'Dataset', 'column_name': 'hdab', 'column_type': 'ref',
        'ref_table': 'Agent', 'term_key': 'health_data_access_body', 'is_entity': False,
        'label_en': 'Health Data Access Body',
        'description_en': 'The authority responsible for granting access to this health dataset.',
        'display_order': 20,
    },
    {
        'table_name': 'Dataset', 'column_name': 'catalog', 'column_type': 'ref',
        'ref_table': 'Catalog', 'term_key': 'in_catalog', 'is_entity': False,
        'label_en': 'Catalogue',
        'description_en': 'The catalogue in which this dataset is published.',
        'display_order': 21,
    },
    # ── Distribution ──────────────────────────────────────────────────────────
    {
        'table_name': 'Distribution', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'distribution_entity', 'is_entity': True,
        'label_en': 'Distribution',
        'description_en': 'A specific representation of a dataset, modelled as a tabular resource.',
        'display_order': 0,
    },
    {
        'table_name': 'Distribution', 'column_name': 'name', 'column_type': 'string',
        'ref_table': None, 'term_key': 'identifier', 'is_entity': False,
        'label_en': 'Distribution ID',
        'description_en': 'A unique identifier for this distribution within the system.',
        'display_order': 1,
    },
    {
        'table_name': 'Distribution', 'column_name': 'title', 'column_type': 'string',
        'ref_table': None, 'term_key': 'title', 'is_entity': False,
        'label_en': 'Title',
        'description_en': 'Human-readable name of the distribution.',
        'display_order': 2,
    },
    {
        'table_name': 'Distribution', 'column_name': 'description', 'column_type': 'text',
        'ref_table': None, 'term_key': 'description', 'is_entity': False,
        'label_en': 'Description',
        'description_en': 'A free-text description of the distribution content and format.',
        'display_order': 3,
    },
    {
        'table_name': 'Distribution', 'column_name': 'format', 'column_type': 'string',
        'ref_table': None, 'term_key': 'format', 'is_entity': False,
        'label_en': 'Format',
        'description_en': 'The file or media format of this distribution.',
        'display_order': 4,
    },
    {
        'table_name': 'Distribution', 'column_name': 'conformedTo', 'column_type': 'string',
        'ref_table': None, 'term_key': 'conforms_to', 'is_entity': False,
        'label_en': 'Conforms To',
        'description_en': 'A standard or schema that this distribution conforms to.',
        'display_order': 5,
    },
    {
        'table_name': 'Distribution', 'column_name': 'accessURL', 'column_type': 'string',
        'ref_table': None, 'term_key': 'access_url', 'is_entity': False,
        'label_en': 'Access URL',
        'description_en': 'A URL through which this distribution of the dataset can be accessed.',
        'display_order': 6,
    },
    {
        'table_name': 'Distribution', 'column_name': 'applicableLegislation', 'column_type': 'string',
        'ref_table': None, 'term_key': 'applicable_legislation', 'is_entity': False,
        'label_en': 'Applicable Legislation',
        'description_en': 'The legal act or regulation applicable to this distribution.',
        'display_order': 7,
    },
    {
        'table_name': 'Distribution', 'column_name': 'byteSize', 'column_type': 'integer',
        'ref_table': None, 'term_key': 'byte_size', 'is_entity': False,
        'label_en': 'Byte Size',
        'description_en': 'The size of this distribution file in bytes.',
        'display_order': 8,
    },
    {
        'table_name': 'Distribution', 'column_name': 'rights', 'column_type': 'string',
        'ref_table': None, 'term_key': 'rights', 'is_entity': False,
        'label_en': 'Rights',
        'description_en': 'A statement about rights associated with this distribution.',
        'display_order': 9,
    },
    {
        'table_name': 'Distribution', 'column_name': 'dataset_name', 'column_type': 'string',
        'ref_table': 'Dataset', 'term_key': 'distribution_dataset_fk', 'is_entity': False,
        'label_en': 'Dataset ID',
        'description_en': 'FK reference to the parent Dataset identifier.',
        'display_order': 10,
    },
    # ── Attribute ─────────────────────────────────────────────────────────────
    {
        'table_name': 'Attribute', 'column_name': None, 'column_type': None,
        'ref_table': None, 'term_key': 'attribute_entity', 'is_entity': True,
        'label_en': 'Table Column',
        'description_en': 'A column definition within a tabular distribution.',
        'display_order': 0,
    },
    {
        'table_name': 'Attribute', 'column_name': 'distribution_name', 'column_type': 'string',
        'ref_table': 'Distribution', 'term_key': 'attribute_distribution_fk', 'is_entity': False,
        'label_en': 'Distribution ID',
        'description_en': 'FK reference to the parent Distribution identifier.',
        'display_order': 1,
    },
    {
        'table_name': 'Attribute', 'column_name': 'name', 'column_type': 'string',
        'ref_table': None, 'term_key': 'csvw_name', 'is_entity': False,
        'label_en': 'Column ID',
        'description_en': 'The machine-readable identifier of this column within the distribution.',
        'display_order': 2,
    },
    {
        'table_name': 'Attribute', 'column_name': 'title', 'column_type': 'string',
        'ref_table': None, 'term_key': 'csvw_title', 'is_entity': False,
        'label_en': 'Column Name',
        'description_en': 'A human-readable title for this column.',
        'display_order': 3,
    },
    {
        'table_name': 'Attribute', 'column_name': 'description', 'column_type': 'text',
        'ref_table': None, 'term_key': 'description', 'is_entity': False,
        'label_en': 'Description',
        'description_en': 'A free-text description of the column content and purpose.',
        'display_order': 4,
    },
    {
        'table_name': 'Attribute', 'column_name': 'datatype', 'column_type': 'string',
        'ref_table': None, 'term_key': 'csvw_datatype', 'is_entity': False,
        'label_en': 'Column Datatype',
        'description_en': 'The data type of values stored in this column.',
        'display_order': 5,
    },
    {
        'table_name': 'Attribute', 'column_name': 'property_url', 'column_type': 'string',
        'ref_table': None, 'term_key': 'csvw_property_url', 'is_entity': False,
        'label_en': 'Property URL',
        'description_en': 'URL identifying the RDF property corresponding to values in this column.',
        'display_order': 6,
    },
]
