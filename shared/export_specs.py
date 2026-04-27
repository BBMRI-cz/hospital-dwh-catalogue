"""Declarative field specs for HealthDCAT-AP exports."""

from __future__ import annotations

from shared.export_terms import (
    ExportEntity,
    ExportFieldSpec,
    ExportRdfClass,
    ExportValueKind,
)

CATALOG_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.CATALOGUE, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.CATALOGUE,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.CATALOGUE,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
)

DATASET_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.DATASET, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.DATASET,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'identifier',
        ExportEntity.DATASET,
        'identifier',
        ExportValueKind.TYPED_ANY_URI,
    ),
    ExportFieldSpec('version', ExportEntity.DATASET, 'version', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'theme',
        ExportEntity.DATASET,
        'theme',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'conforms_to',
        ExportEntity.DATASET,
        'conformsTo',
        ExportValueKind.LITERAL_OR_ID_LIST,
        reference_classes=(ExportRdfClass.STANDARD,),
    ),
    ExportFieldSpec('issued', ExportEntity.DATASET, 'releaseDate', ExportValueKind.TYPED_DATETIME),
    ExportFieldSpec(
        'modified',
        ExportEntity.DATASET,
        'modificationDate',
        ExportValueKind.TYPED_DATETIME,
    ),
    ExportFieldSpec('keywords', ExportEntity.DATASET, 'keyword', ExportValueKind.KEYWORD_LIST),
    ExportFieldSpec(
        'access_rights',
        ExportEntity.DATASET,
        'accessRights',
        ExportValueKind.ID,
        reference_classes=(ExportRdfClass.RIGHTS_STATEMENT, ExportRdfClass.CONCEPT),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.DATASET,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
    ExportFieldSpec(
        'health_category',
        ExportEntity.DATASET,
        'healthCategory',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
    ExportFieldSpec(
        'type',
        ExportEntity.DATASET,
        'type',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.CONCEPT,),
        reference_labels=True,
    ),
)

DISTRIBUTION_FIELDS: tuple[ExportFieldSpec, ...] = (
    ExportFieldSpec('title', ExportEntity.DISTRIBUTION, 'title', ExportValueKind.LITERAL),
    ExportFieldSpec(
        'description',
        ExportEntity.DISTRIBUTION,
        'description',
        ExportValueKind.LITERAL,
    ),
    ExportFieldSpec(
        'access_url',
        ExportEntity.DISTRIBUTION,
        'accessUrl',
        ExportValueKind.ID,
    ),
    ExportFieldSpec(
        'applicable_legislation',
        ExportEntity.DISTRIBUTION,
        'applicableLegislation',
        ExportValueKind.ID_LIST,
        reference_classes=(ExportRdfClass.LEGAL_RESOURCE,),
    ),
    ExportFieldSpec(
        'format',
        ExportEntity.DISTRIBUTION,
        'format',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.MEDIA_TYPE_OR_EXTENT,),
    ),
    ExportFieldSpec(
        'conforms_to',
        ExportEntity.DISTRIBUTION,
        'linkedSchemas',
        ExportValueKind.LITERAL_OR_ID_LIST,
        reference_classes=(ExportRdfClass.STANDARD,),
    ),
    ExportFieldSpec(
        'byte_size',
        ExportEntity.DISTRIBUTION,
        'byteSize',
        ExportValueKind.TYPED_NON_NEGATIVE_INTEGER,
    ),
    ExportFieldSpec(
        'rights',
        ExportEntity.DISTRIBUTION,
        'rights',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.RIGHTS_STATEMENT,),
    ),
    ExportFieldSpec(
        'licence',
        ExportEntity.DISTRIBUTION,
        'licence',
        ExportValueKind.LITERAL_OR_ID,
        reference_classes=(ExportRdfClass.LICENCE_DOCUMENT,),
    ),
    ExportFieldSpec(
        'release_date',
        ExportEntity.DISTRIBUTION,
        'releaseDate',
        ExportValueKind.TYPED_DATETIME,
    ),
    ExportFieldSpec(
        'modification_date',
        ExportEntity.DISTRIBUTION,
        'modificationDate',
        ExportValueKind.TYPED_DATETIME,
    ),
)
