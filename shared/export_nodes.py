"""Build JSON-LD resource nodes from export DTOs."""

from __future__ import annotations

from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
)
from shared.email_utils import mailto_iri, normalise_email
from shared.export_graph import JsonLdGraphBuilder
from shared.export_specs import CATALOG_FIELDS, DATASET_FIELDS, DISTRIBUTION_FIELDS
from shared.export_terms import ExportEntity, ExportFieldSpec, ExportRdfClass
from shared.export_types import JsonLdIdRef, JsonLdNode
from shared.export_values import id_ref, is_http_uri, jsonld_field_value


def catalog_iri(name: str) -> str | None:
    return name if is_http_uri(name) else None


def dataset_iri(identifier: str | None = None) -> str | None:
    return identifier if identifier else None


def distribution_iri(access_url: str | None = None) -> str | None:
    return access_url if access_url else None


def agent_iri(name: str) -> str | None:
    return name if is_http_uri(name) else None


def contact_point_iri(contact_point: ExportContactPoint) -> str | None:
    if contact_point.contact_page:
        return contact_point.contact_page
    return mailto_iri(contact_point.email)


def apply_field_specs(
    node: JsonLdNode,
    source: object,
    field_specs: tuple[ExportFieldSpec, ...],
    builder: JsonLdGraphBuilder,
) -> None:
    for spec in field_specs:
        property_name = builder.profile.property(spec)
        if property_name is None:
            continue
        raw_value = getattr(source, spec.attr, None)
        value = jsonld_field_value(raw_value, spec.value_kind, builder.profile)
        if value is None:
            continue

        node[property_name] = value
        if spec.reference_classes:
            builder.add_reference_nodes(
                raw_value,
                spec.reference_classes,
                labels=spec.reference_labels,
            )


def provenance_node(value: str, builder: JsonLdGraphBuilder) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.rdf_class(ExportRdfClass.PROVENANCE_STATEMENT)])
    builder.set_property(node, builder.profile.term('dct:description'), value)
    return node


def build_contact_point_node(
    contact_point: ExportContactPoint,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(
        node,
        [builder.profile.named_class('ContactPoint'), builder.profile.named_class('Kind')],
    )
    iri = contact_point_iri(contact_point)
    if iri is not None:
        node['@id'] = iri
    email = normalise_email(contact_point.email)
    email_iri = mailto_iri(email)
    if email and email_iri:
        builder.set_property(node, builder.profile.term('cv:email'), email)
        builder.set_property(
            node,
            builder.profile.term('vcard:hasEmail'),
            id_ref(email_iri),
        )
    if contact_point.contact_page:
        builder.set_property(
            node,
            builder.profile.term('cv:contactPage'),
            id_ref(contact_point.contact_page),
        )
        builder.set_property(
            node,
            builder.profile.term('vcard:hasURL'),
            id_ref(contact_point.contact_page),
        )
    return node


def ensure_contact_point(
    contact_point: ExportContactPoint | None,
    builder: JsonLdGraphBuilder,
) -> JsonLdIdRef | JsonLdNode | None:
    if contact_point is None:
        return None
    node = build_contact_point_node(contact_point, builder)
    iri = node.get('@id')
    if isinstance(iri, str):
        builder.append(node)
        return id_ref(iri)
    return node


def build_agent_node(agent: ExportAgent, builder: JsonLdGraphBuilder) -> JsonLdIdRef | JsonLdNode:
    contact_point_value = ensure_contact_point(agent.contact_point, builder)
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.named_class('Agent')])
    builder.set_property(node, builder.profile.term('foaf:name'), agent.name)
    iri = agent_iri(agent.name)
    if iri is not None:
        node['@id'] = iri
    if agent.description:
        builder.set_property(node, builder.profile.term('dct:description'), agent.description)
    if contact_point_value is not None:
        builder.set_property(node, builder.profile.term('cv:contactPoint'), contact_point_value)
    if iri is not None:
        builder.append(node)
        return id_ref(iri)
    return node


def build_table_group(
    distribution: ExportDistribution,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode | None:
    if not distribution.tables:
        return None
    table_property = builder.profile.term('csvw:table')
    column_property = builder.profile.term('csvw:column')
    if table_property is None or column_property is None:
        return None

    table_group: JsonLdNode = {table_property: []}
    builder.set_type(table_group, [builder.profile.named_class('TableGroup')])

    tables = table_group[table_property]
    assert isinstance(tables, list)
    for table in distribution.tables:
        table_node: JsonLdNode = {column_property: []}
        builder.set_type(table_node, [builder.profile.named_class('Table')])
        builder.set_property(table_node, builder.profile.term('csvw:name'), table.name)
        if table.title:
            builder.set_property(table_node, builder.profile.term('dct:title'), table.title)
        if table.description:
            builder.set_property(
                table_node,
                builder.profile.term('dct:description'),
                table.description,
            )
        if table.url:
            builder.set_property(table_node, builder.profile.term('csvw:url'), id_ref(table.url))

        columns = table_node[column_property]
        assert isinstance(columns, list)
        for column in table.columns:
            column_node: JsonLdNode = {}
            builder.set_type(column_node, [builder.profile.named_class('Column')])
            builder.set_property(column_node, builder.profile.term('csvw:name'), column.name)
            if column.title:
                builder.set_property(column_node, builder.profile.term('dct:title'), column.title)
                builder.set_property(column_node, builder.profile.term('csvw:titles'), column.title)
            if column.description:
                builder.set_property(
                    column_node,
                    builder.profile.term('dct:description'),
                    column.description,
                )
            if column.datatype:
                builder.set_property(
                    column_node,
                    builder.profile.term('csvw:datatype'),
                    column.datatype,
                )
            if column.property_url:
                builder.set_property(
                    column_node,
                    builder.profile.term('csvw:propertyUrl'),
                    id_ref(column.property_url),
                )
            columns.append(column_node)

        tables.append(table_node)

    return table_group


def build_distribution_node(
    distribution: ExportDistribution,
    builder: JsonLdGraphBuilder,
) -> JsonLdNode:
    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.entity_type(ExportEntity.DISTRIBUTION)])
    iri = distribution_iri(distribution.access_url)
    if iri is not None:
        node['@id'] = iri

    apply_field_specs(node, distribution, DISTRIBUTION_FIELDS, builder)

    sample = build_table_group(distribution, builder)
    if sample is not None:
        builder.set_property(node, builder.profile.term('adms:sample'), sample)
    return node


def build_dataset_node(
    dataset: ExportDataset,
    builder: JsonLdGraphBuilder,
    *,
    include_distributions: bool = True,
) -> JsonLdNode:
    publisher_value = build_agent_node(dataset.publisher, builder) if dataset.publisher else None
    creator_value = build_agent_node(dataset.creator, builder) if dataset.creator else None
    hdab_value = build_agent_node(dataset.hdab, builder) if dataset.hdab else None
    custodian_value = build_agent_node(dataset.custodian, builder) if dataset.custodian else None
    contact_point_value = ensure_contact_point(dataset.contact_point, builder)

    node: JsonLdNode = {}
    builder.set_type(node, [builder.profile.entity_type(ExportEntity.DATASET)])
    iri = dataset_iri(dataset.identifier)
    if iri is not None:
        node['@id'] = iri

    apply_field_specs(node, dataset, DATASET_FIELDS, builder)

    if publisher_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'publisher'),
            publisher_value,
        )
    if creator_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'creator'),
            creator_value,
        )
    if contact_point_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'contactPoint'),
            contact_point_value,
        )
    if dataset.provenance:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'provenance'),
            provenance_node(dataset.provenance, builder),
        )
    if hdab_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'hdab'),
            hdab_value,
        )
    if custodian_value is not None:
        builder.set_property(
            node,
            builder.profile.property_alias(ExportEntity.DATASET, 'custodian'),
            custodian_value,
        )
    if include_distributions and dataset.distributions:
        dist_refs = [
            id_ref(iri)
            for distribution in dataset.distributions
            if (iri := distribution_iri(distribution.access_url)) is not None
        ]
        if dist_refs:
            builder.set_property(
                node,
                builder.profile.property_alias(ExportEntity.DATASET, 'distribution'),
                dist_refs,
            )
    return node


def add_distributions(dataset: ExportDataset, builder: JsonLdGraphBuilder) -> None:
    for distribution in dataset.distributions:
        builder.append(build_distribution_node(distribution, builder))


def build_catalog_node(
    catalog: ExportCatalog,
    builder: JsonLdGraphBuilder,
    *,
    dataset_refs: list[JsonLdIdRef],
) -> JsonLdNode:
    catalog_node: JsonLdNode = {}
    builder.set_type(catalog_node, [builder.profile.entity_type(ExportEntity.CATALOGUE)])
    builder.set_property(
        catalog_node,
        builder.profile.property_alias(ExportEntity.CATALOGUE, 'dataset'),
        dataset_refs,
    )
    iri = catalog_iri(catalog.name)
    if iri is not None:
        catalog_node['@id'] = iri

    apply_field_specs(catalog_node, catalog, CATALOG_FIELDS, builder)

    if catalog.publisher is not None:
        builder.set_property(
            catalog_node,
            builder.profile.property_alias(ExportEntity.CATALOGUE, 'publisher'),
            build_agent_node(catalog.publisher, builder),
        )
    return catalog_node


def append_dataset_resource(
    dataset: ExportDataset,
    builder: JsonLdGraphBuilder,
    *,
    include_catalog: bool,
    include_distributions: bool = True,
) -> None:
    if include_catalog and dataset.catalog is not None:
        iri = dataset_iri(dataset.identifier)
        dataset_refs = [id_ref(iri)] if iri is not None else []
        builder.append(build_catalog_node(dataset.catalog, builder, dataset_refs=dataset_refs))

    builder.append(
        build_dataset_node(dataset, builder, include_distributions=include_distributions)
    )
    if include_distributions:
        add_distributions(dataset, builder)


def append_catalog_resource(
    catalog: ExportCatalog,
    builder: JsonLdGraphBuilder,
    *,
    include_distributions: bool = True,
) -> None:
    dataset_refs = [
        id_ref(iri)
        for dataset in catalog.datasets
        if (iri := dataset_iri(dataset.identifier)) is not None
    ]
    builder.append(build_catalog_node(catalog, builder, dataset_refs=dataset_refs))

    for dataset in catalog.datasets:
        append_dataset_resource(
            dataset,
            builder,
            include_catalog=False,
            include_distributions=include_distributions,
        )
