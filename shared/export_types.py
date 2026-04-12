"""Typed JSON-LD payloads used by HealthDCAT-AP export helpers."""

from __future__ import annotations

from typing import NotRequired, Required, TypedDict

from shared.dtos import ExportCatalog, ExportDataset

ExportResource = ExportDataset | ExportCatalog

JsonLdContext = dict[str, str]

JsonLdIdRef = TypedDict('JsonLdIdRef', {'@id': Required[str]})

JsonLdTypedValue = TypedDict(
    'JsonLdTypedValue',
    {
        '@type': Required[str],
        '@value': Required[str],
    },
)

JsonLdLiteralOrUri = str | JsonLdIdRef
JsonLdLiteralOrUriList = list[JsonLdLiteralOrUri]
JsonLdIdRefList = list[JsonLdIdRef]

JsonLdColumnNode = TypedDict(
    'JsonLdColumnNode',
    {
        '@type': Required[str],
        'csvw:name': Required[str],
        'dct:title': NotRequired[str],
        'dct:description': NotRequired[str],
        'csvw:datatype': NotRequired[str],
        'csvw:propertyUrl': NotRequired[JsonLdIdRef],
    },
    total=False,
)

JsonLdTableNode = TypedDict(
    'JsonLdTableNode',
    {
        '@type': Required[str],
        'csvw:name': Required[str],
        'csvw:column': Required[list[JsonLdColumnNode]],
        'dct:title': NotRequired[str],
        'dct:description': NotRequired[str],
        'csvw:url': NotRequired[JsonLdIdRef],
    },
    total=False,
)

JsonLdTableGroupNode = TypedDict(
    'JsonLdTableGroupNode',
    {
        '@type': Required[str],
        'csvw:table': Required[list[JsonLdTableNode]],
    },
    total=False,
)

JsonLdContactPointNode = TypedDict(
    'JsonLdContactPointNode',
    {
        '@id': NotRequired[str],
        '@type': Required[list[str]],
        'cv:email': NotRequired[str],
        'vcard:hasEmail': NotRequired[JsonLdIdRef],
        'cv:contactPage': NotRequired[JsonLdIdRef],
        'vcard:hasURL': NotRequired[JsonLdIdRef],
    },
    total=False,
)

JsonLdContactPointValue = JsonLdIdRef | JsonLdContactPointNode

JsonLdAgentNode = TypedDict(
    'JsonLdAgentNode',
    {
        '@id': NotRequired[str],
        '@type': Required[str],
        'foaf:name': Required[str],
        'dct:description': NotRequired[str],
        'cv:contactPoint': NotRequired[JsonLdContactPointValue],
    },
    total=False,
)

JsonLdAgentValue = JsonLdIdRef | JsonLdAgentNode

JsonLdDistributionNode = TypedDict(
    'JsonLdDistributionNode',
    {
        '@id': NotRequired[str],
        '@type': Required[str],
        'dct:title': NotRequired[str],
        'dct:description': NotRequired[str],
        'dcat:accessURL': NotRequired[JsonLdIdRef],
        'dcatap:applicableLegislation': NotRequired[JsonLdIdRef | JsonLdIdRefList],
        'dct:format': NotRequired[JsonLdLiteralOrUri],
        'dct:conformsTo': NotRequired[JsonLdLiteralOrUri | JsonLdLiteralOrUriList],
        'dcat:byteSize': NotRequired[int],
        'dct:rights': NotRequired[JsonLdLiteralOrUri],
        'dct:license': NotRequired[JsonLdLiteralOrUri],
        'dct:issued': NotRequired[JsonLdTypedValue],
        'dct:modified': NotRequired[JsonLdTypedValue],
        'adms:sample': NotRequired[JsonLdTableGroupNode],
    },
    total=False,
)

JsonLdDatasetNode = TypedDict(
    'JsonLdDatasetNode',
    {
        '@id': NotRequired[str],
        '@type': Required[str],
        'dct:title': NotRequired[str],
        'dct:description': NotRequired[str],
        'dct:identifier': NotRequired[JsonLdTypedValue],
        'dcat:version': NotRequired[str],
        'dcat:theme': NotRequired[JsonLdIdRef | JsonLdIdRefList],
        'dct:publisher': NotRequired[JsonLdAgentValue],
        'dct:creator': NotRequired[JsonLdAgentValue],
        'dct:conformsTo': NotRequired[JsonLdLiteralOrUri | JsonLdLiteralOrUriList],
        'dct:issued': NotRequired[JsonLdTypedValue],
        'dct:modified': NotRequired[JsonLdTypedValue],
        'dcat:keyword': NotRequired[list[str]],
        'dct:source': NotRequired[JsonLdIdRef],
        'dcat:contactPoint': NotRequired[JsonLdContactPointValue],
        'dct:provenance': NotRequired[str],
        'dct:accessRights': NotRequired[JsonLdIdRef],
        'dcatap:applicableLegislation': NotRequired[JsonLdIdRef | JsonLdIdRefList],
        'healthdcatap:healthCategory': NotRequired[JsonLdIdRef | JsonLdIdRefList],
        'healthdcatap:hdab': NotRequired[JsonLdAgentValue],
        'geodcatap:custodian': NotRequired[JsonLdAgentValue],
        'dct:type': NotRequired[JsonLdIdRef | JsonLdIdRefList],
        'dcat:distribution': NotRequired[JsonLdIdRefList],
    },
    total=False,
)

JsonLdCatalogNode = TypedDict(
    'JsonLdCatalogNode',
    {
        '@id': NotRequired[str],
        '@type': Required[str],
        'dcat:dataset': Required[JsonLdIdRefList],
        'dct:title': NotRequired[str],
        'dct:description': NotRequired[str],
        'dcatap:applicableLegislation': NotRequired[JsonLdIdRef],
        'dct:publisher': NotRequired[JsonLdAgentValue],
    },
    total=False,
)

JsonLdGraphNode = (
    JsonLdCatalogNode
    | JsonLdDatasetNode
    | JsonLdDistributionNode
    | JsonLdAgentNode
    | JsonLdContactPointNode
)

JsonLdGraph = list[JsonLdGraphNode]

JsonLdDocument = TypedDict(
    'JsonLdDocument',
    {
        '@context': Required[JsonLdContext],
        '@graph': Required[JsonLdGraph],
    },
)
