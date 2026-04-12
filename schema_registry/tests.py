"""
Schema Registry  Tests
========================

Tests for the in-memory registry loader (schema_registry.registry) and the
public service layer (schema_registry.services).

No database is involved.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypeGuard, cast

from django.conf import settings
from django.test import TestCase, override_settings

from schema_registry.registry import _load, invalidate_cache
from schema_registry.types import SchemaRegistryPayload
from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportColumn,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
    ExportTable,
)
from shared.export_types import (
    JsonLdDatasetNode,
    JsonLdDistributionNode,
    JsonLdDocument,
    JsonLdGraphNode,
)

# Absolute path to the release-6 directory inside the submodule.
_RELEASE_6 = settings.BASE_DIR / 'health_dcat_ap' / 'public' / 'releases' / 'release-6'


def _is_distribution_node(node: JsonLdGraphNode) -> TypeGuard[JsonLdDistributionNode]:
    return node.get('@type') == 'dcat:Distribution'


def _node_has_type(node: JsonLdGraphNode, rdf_type: str) -> bool:
    value = node.get('@type')
    if isinstance(value, list):
        return rdf_type in value
    return value == rdf_type


class RegistryParserTest(TestCase):
    """Tests for the SHACL + cardinality-JSON parser (schema_registry.registry)."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def _load_release6(self) -> dict:
        term_dict, _prefix_map = _load(_RELEASE_6)
        return term_dict

    #  Basic structure

    def test_returns_non_empty_dict(self) -> None:
        registry = self._load_release6()
        self.assertIsInstance(registry, dict)
        self.assertGreater(len(registry), 0)

    def test_keys_are_prefixed_strings(self) -> None:
        registry = self._load_release6()
        for key in registry:
            self.assertIn(':', key, f'Key "{key}" is not in prefix:local form')

    def test_each_entry_has_required_fields(self) -> None:
        registry = self._load_release6()
        required_fields = {
            'prefix',
            'local_name',
            'uri',
            'requirement',
            'cardinality',
            'label',
            'description',
        }
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertEqual(set(entry.keys()), required_fields)

    #  Requirement values

    def test_requirement_values_are_valid(self) -> None:
        valid = {'mandatory', 'recommended', 'optional', 'deprecated'}
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertIn(entry['requirement'], valid)

    def test_has_mandatory_terms(self) -> None:
        registry = self._load_release6()
        mandatory = [k for k, v in registry.items() if v['requirement'] == 'mandatory']
        self.assertGreater(len(mandatory), 0)

    #  Known base DCAT-AP terms

    def test_dct_title_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dct:title', registry)
        entry = registry['dct:title']
        self.assertEqual(entry['prefix'], 'dct')
        self.assertEqual(entry['local_name'], 'title')
        self.assertIn('purl.org/dc/terms', entry['uri'])

    def test_dct_description_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dct:description', registry)

    def test_dcat_keyword_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('dcat:keyword', registry)

    def test_dct_publisher_is_recommended(self) -> None:
        """JSON overrides SHACL: publisher is Recommended at dataset level."""
        registry = self._load_release6()
        self.assertIn('dct:publisher', registry)
        self.assertEqual(registry['dct:publisher']['requirement'], 'recommended')

    #  URI consistency

    def test_uri_matches_prefix_and_local_name(self) -> None:
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertTrue(entry['uri'].endswith(entry['local_name']))

    def test_no_empty_uris(self) -> None:
        registry = self._load_release6()
        for key, entry in registry.items():
            with self.subTest(semantics=key):
                self.assertTrue(entry['uri'], f'Empty URI for "{key}"')

    #  HealthDCAT-AP extension terms

    def test_healthdcat_healthcategory_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('healthdcatap:healthCategory', registry)
        entry = registry['healthdcatap:healthCategory']
        self.assertEqual(entry['prefix'], 'healthdcatap')
        self.assertEqual(entry['local_name'], 'healthCategory')
        self.assertIn('healthdataportal.eu', entry['uri'])
        self.assertEqual(entry['requirement'], 'mandatory')

    def test_healthdcat_hdab_present(self) -> None:
        registry = self._load_release6()
        self.assertIn('healthdcatap:hdab', registry)
        entry = registry['healthdcatap:hdab']
        self.assertEqual(entry['requirement'], 'mandatory')

    def test_synthesized_extension_uris_use_prefix_map(self) -> None:
        from schema_registry.registry import _merge_healthdcat_terms

        payload = {
            'PUBLIC': {
                'health category': {
                    'card': '1..*',
                    'requirement': 'Mandatory',
                    'definition': 'Synthetic test term.',
                    'usage_note': (
                        'RDF example: '
                        '<a href="#healthdcataphealthCategory">healthdcatap:healthCategory</a>'
                    ),
                },
                'custodian': {
                    'card': '0..1',
                    'requirement': 'Recommended',
                    'definition': 'Synthetic geodcatap test term.',
                    'usage_note': (
                        'RDF example: <a href="#geodcatapcustodian">geodcatap:custodian</a>'
                    ),
                },
            }
        }

        with TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / 'healthdcat-cardinality-rules.json'
            json_path.write_text(json.dumps(payload), encoding='utf-8')

            result: SchemaRegistryPayload = {}
            _merge_healthdcat_terms(
                json_path,
                result,
                {
                    'healthdcatap': 'https://example.org/health#',
                    'geodcatap': 'https://example.org/geodcatap#',
                },
            )

        self.assertIn('healthdcatap:healthCategory', result)
        self.assertEqual(
            result['healthdcatap:healthCategory']['uri'],
            'https://example.org/health#healthCategory',
        )
        self.assertIn('geodcatap:custodian', result)
        self.assertEqual(
            result['geodcatap:custodian']['uri'],
            'https://example.org/geodcatap#custodian',
        )

    #  Namespace prefix map

    def test_namespace_prefixes_include_healthdcat_specific(self) -> None:
        """
        Prefixes declared only in html/shacl/public-shapes.ttl (not in the base
        DCAT-AP SHACL TTL) must be present in the returned prefix map.
        """
        from schema_registry.registry import get_namespace_prefixes

        prefixes = get_namespace_prefixes(_RELEASE_6)
        for expected in ('healthdcatap', 'geodcatap', 'dcatap', 'dpv', 'org', 'csvw'):
            with self.subTest(prefix=expected):
                self.assertIn(expected, prefixes, f'Prefix "{expected}" missing from namespace map')
                self.assertTrue(prefixes[expected].startswith('http'))

    #  Edge cases

    def test_missing_release_dir_returns_empty_dict(self) -> None:
        term_dict, prefix_map = _load(Path('/nonexistent/path/release-99'))
        self.assertEqual(term_dict, {})
        self.assertEqual(prefix_map, {})

    def test_result_is_json_serialisable(self) -> None:
        registry = self._load_release6()
        serialised = json.dumps(registry)
        self.assertIsInstance(serialised, str)

    #  Cardinality

    def test_cardinality_set_for_json_matched_terms(self) -> None:
        """Terms matched in the cardinality JSON must have a non-empty cardinality."""
        registry = self._load_release6()
        self.assertNotEqual(registry['dct:title']['cardinality'], '')
        self.assertNotEqual(registry['healthdcatap:healthCategory']['cardinality'], '')

    def test_cardinality_format(self) -> None:
        """Cardinality values must follow the 'min..max' pattern."""
        registry = self._load_release6()
        for key, entry in registry.items():
            card = entry['cardinality']
            if card:
                with self.subTest(semantics=key):
                    self.assertRegex(card, r'^\d+\.\.([\d*]+)$')

    #  Requirement upgrade from JSON

    def test_dcat_keyword_is_recommended(self) -> None:
        """JSON upgrades dcat:keyword from SHACL 'optional' to 'recommended'."""
        registry = self._load_release6()
        self.assertIn('dcat:keyword', registry)
        self.assertEqual(registry['dcat:keyword']['requirement'], 'recommended')


class RegistryCacheTest(TestCase):
    """Tests for the module-level lazy cache in schema_registry.registry."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def test_get_registry_caches_result(self) -> None:
        from schema_registry.registry import get_registry

        first = get_registry(_RELEASE_6)
        second = get_registry(_RELEASE_6)
        self.assertIs(first, second)

    def test_invalidate_clears_cache(self) -> None:
        from schema_registry.registry import get_registry

        first = get_registry(_RELEASE_6)
        invalidate_cache()
        second = get_registry(_RELEASE_6)
        # Should be a fresh dict (different object)
        self.assertIsNot(first, second)

    def test_cache_keyed_by_path(self) -> None:
        """Different release_dir values get independent cache entries."""
        from schema_registry.registry import get_registry

        good = get_registry(_RELEASE_6)
        bad = get_registry(Path('/nonexistent/path/release-99'))
        # The valid path returns data, the missing path returns empty
        self.assertGreater(len(good), 0)
        self.assertEqual(len(bad), 0)
        # Calling the valid path again still returns the cached data (not empty)
        self.assertIs(get_registry(_RELEASE_6), good)


class ServiceLayerTest(TestCase):
    """Tests for the public service API (schema_registry.services)."""

    def setUp(self) -> None:
        invalidate_cache()

    def tearDown(self) -> None:
        invalidate_cache()

    def test_get_schema_dict_returns_dict(self) -> None:
        from schema_registry.services import get_schema_dict

        result = get_schema_dict()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_get_schema_dict_uses_settings_version(self) -> None:
        from schema_registry.services import get_schema_dict

        with override_settings(HEALTH_DCAT_VERSION='release-6'):
            invalidate_cache()
            result = get_schema_dict()
        self.assertIn('dct:title', result)

    def test_get_schema_dict_returns_empty_for_unknown_version(self) -> None:
        from schema_registry.services import get_schema_dict

        with override_settings(HEALTH_DCAT_VERSION='release-999'):
            invalidate_cache()
            result = get_schema_dict()
        self.assertEqual(result, {})

    def test_get_context_prefixes_returns_dict(self) -> None:
        from schema_registry.services import get_context_prefixes

        result = get_context_prefixes()
        self.assertIsInstance(result, dict)
        self.assertIn('dct', result)
        self.assertTrue(result['dct'].startswith('http'))


class BuildJsonldContextTest(TestCase):
    """Tests for the prefix-filtering behaviour of build_jsonld() in shared.export."""

    def _make_contact_point(
        self,
        *,
        identifier: str = 'cp-1',
        email: str | None = 'data@acme.example',
        contact_page: str | None = 'https://example.com/contact',
    ) -> ExportContactPoint:
        return ExportContactPoint(
            app='warehouse',
            identifier=identifier,
            email=email,
            contact_page=contact_page,
        )

    def _make_agent(
        self,
        *,
        name: str,
        contact_point: ExportContactPoint | None,
    ) -> ExportAgent:
        return ExportAgent(app='warehouse', name=name, contact_point=contact_point)

    def _make_dataset(self, *, with_tables: bool = False) -> ExportDataset:
        dataset_cp = self._make_contact_point(identifier='dataset-cp')
        agent_cp = self._make_contact_point(identifier='agent-cp')
        publisher = self._make_agent(name='Acme Hospital', contact_point=agent_cp)
        hdab = self._make_agent(name='Acme HDAB', contact_point=agent_cp)
        custodian = self._make_agent(name='Acme Custodian', contact_point=agent_cp)

        tables = []
        if with_tables:
            tables = [
                ExportTable(
                    name='patient_encounters',
                    title='Patient Encounters',
                    description='Encounter records',
                    url='http://example.com/patient_encounters',
                    columns=[
                        ExportColumn(
                            name='encounter_id',
                            title='Encounter ID',
                            description='Unique encounter identifier',
                            datatype='integer',
                        ),
                        ExportColumn(
                            name='diagnosis_code',
                            title='Diagnosis Code',
                            description='ICD-10 code',
                            datatype='string',
                            property_url='http://purl.bioontology.org/ontology/ICD10',
                        ),
                    ],
                )
            ]

        catalog = ExportCatalog(
            app='warehouse',
            name='warehouse-cat',
            title='Warehouse Catalogue',
            description='Warehouse catalogue description',
            applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
            publisher=publisher,
        )

        return ExportDataset(
            app='warehouse',
            name='test-ds',
            title='Test dataset',
            description='A test dataset',
            identifier='https://example.com/dataset/test-ds',
            type='http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
            theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
            keywords=['health'],
            custodian=custodian,
            publisher=publisher,
            hdab=hdab,
            access_rights='http://publications.europa.eu/resource/authority/access-right/PUBLIC',
            health_category='http://healthdataportal.eu/ns/health#clinical',
            applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
            contact_point=dataset_cp,
            catalog=catalog,
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='dist-1',
                    title='CSV file',
                    access_url='http://example.com/dist',
                    format='http://publications.europa.eu/resource/authority/file-type/CSV',
                    applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
                    tables=tables,
                )
            ],
        )

    def _build(self, ds: ExportDataset | None = None) -> JsonLdDocument:
        from shared.export import build_jsonld

        return build_jsonld(ds if ds is not None else self._make_dataset())

    def test_context_is_first_key(self) -> None:
        result = self._build()
        self.assertEqual(next(iter(result.keys())), '@context')

    def test_full_dataset_contains_expected_prefixes(self) -> None:
        context = self._build()['@context']
        expected = {
            'cv',
            'dcat',
            'dct',
            'healthdcatap',
            'dcatap',
            'foaf',
            'vcard',
            'geodcatap',
            'xsd',
        }
        self.assertEqual(set(context.keys()), expected)

    def test_no_contact_point_drops_vcard(self) -> None:
        ds = self._make_dataset()
        ds.contact_point = None
        ds.publisher = None
        ds.hdab = None
        ds.custodian = None
        ds.catalog = ExportCatalog(
            app='warehouse',
            name='warehouse-cat',
            title='Warehouse Catalogue',
            description='Warehouse catalogue description',
            applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
            publisher=None,
        )
        context = self._build(ds)['@context']
        self.assertNotIn('vcard', context)

    def test_no_custodian_drops_geodcatap(self) -> None:
        ds = self._make_dataset()
        ds.custodian = None
        context = self._build(ds)['@context']
        self.assertNotIn('geodcatap', context)

    def test_unused_ttl_prefixes_absent(self) -> None:
        context = self._build()['@context']
        unused = {
            'prov',
            'rdf',
            'rdfs',
            'shacl',
            'skos',
            'cc',
            'lcon',
            'owl',
            'odrl',
            'schema',
            'sh',
            'spdx',
            'time',
            'dpv',
        }
        for prefix in unused:
            with self.subTest(prefix=prefix):
                self.assertNotIn(prefix, context)

    def test_context_values_are_uris(self) -> None:
        context = self._build()['@context']
        for prefix, uri in context.items():
            with self.subTest(prefix=prefix):
                self.assertTrue(uri.startswith('http'), f'{prefix!r} → {uri!r} is not an http URI')

    # ── CSVW table/column export ─────────────────────────────────────────────

    def _distribution_node(self, result: JsonLdDocument) -> JsonLdDistributionNode:
        return next(node for node in result['@graph'] if _is_distribution_node(node))

    def test_tables_emit_csvw_hierarchy(self) -> None:
        result = self._build(self._make_dataset(with_tables=True))
        dist = self._distribution_node(result)
        self.assertIn('adms:sample', dist)
        tg = dist.get('adms:sample')
        self.assertIsNotNone(tg)
        if tg is None:
            self.fail('Expected adms:sample in distribution node')
        self.assertEqual(tg['@type'], 'csvw:TableGroup')
        tables = tg['csvw:table']
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table['@type'], 'csvw:Table')
        self.assertEqual(table.get('dct:title'), 'Patient Encounters')
        self.assertEqual(table.get('csvw:url'), {'@id': 'http://example.com/patient_encounters'})
        cols = table['csvw:column']
        self.assertEqual(len(cols), 2)
        self.assertEqual(cols[0]['csvw:name'], 'encounter_id')
        self.assertEqual(cols[0].get('csvw:datatype'), 'integer')
        self.assertNotIn('csvw:propertyUrl', cols[0])
        self.assertEqual(
            cols[1].get('csvw:propertyUrl'),
            {'@id': 'http://purl.bioontology.org/ontology/ICD10'},
        )

    def test_tables_add_csvw_and_adms_prefixes(self) -> None:
        context = self._build(self._make_dataset(with_tables=True))['@context']
        self.assertIn('csvw', context)
        self.assertIn('adms', context)

    def test_no_tables_omits_csvw(self) -> None:
        context = self._build()['@context']
        self.assertNotIn('csvw', context)
        self.assertNotIn('adms', context)

    def test_empty_tables_list_omits_sample(self) -> None:
        ds = self._make_dataset()
        dist = self._distribution_node(self._build(ds))
        self.assertNotIn('adms:sample', dist)

    def test_nodes_use_provided_identifiers_and_keep_related_nodes(self) -> None:
        result = self._build()

        dataset_node = next(
            node for node in result['@graph'] if _node_has_type(node, 'dcat:Dataset')
        )
        distribution_node = self._distribution_node(result)
        catalog_node = next(
            node for node in result['@graph'] if _node_has_type(node, 'dcat:Catalog')
        )
        agent_nodes = [node for node in result['@graph'] if _node_has_type(node, 'foaf:Agent')]
        contact_point_nodes = [
            node for node in result['@graph'] if _node_has_type(node, 'cv:ContactPoint')
        ]
        dataset_values = cast(dict[str, object], dataset_node)
        catalog_values = cast(dict[str, object], catalog_node)

        self.assertEqual(dataset_values.get('@id'), 'https://example.com/dataset/test-ds')
        self.assertEqual(distribution_node['@id'], 'http://example.com/dist')
        self.assertNotIn('@id', catalog_values)
        self.assertEqual(len(agent_nodes), 0)
        self.assertGreaterEqual(len(contact_point_nodes), 1)
        self.assertIn(
            'https://example.com/contact',
            {cast(dict[str, object], node).get('@id') for node in contact_point_nodes},
        )

        dataset_publisher = cast(dict[str, object] | None, dataset_values.get('dct:publisher'))
        self.assertIsNotNone(dataset_publisher)
        if dataset_publisher is None:
            self.fail('Expected dataset publisher in export')
        self.assertEqual(dataset_publisher.get('foaf:name'), 'Acme Hospital')
        self.assertNotIn('@id', dataset_publisher)

        catalog_publisher = cast(dict[str, object] | None, catalog_values.get('dct:publisher'))
        self.assertIsNotNone(catalog_publisher)
        if catalog_publisher is None:
            self.fail('Expected catalog publisher in export')
        self.assertEqual(catalog_publisher.get('foaf:name'), 'Acme Hospital')

        for node in result['@graph']:
            node_id = node.get('@id')
            if node_id is None:
                continue
            self.assertNotIn('urn:hospital-dwh-catalogue', node_id)
            self.assertNotIn('/api/jsonld#', node_id)
            self.assertNotIn('/api/metadata/', node_id)

    def test_source_uses_provided_dataset_identifier(self) -> None:
        ds = self._make_dataset()
        ds.source_name = 'source-ds'
        ds.source_identifier = 'https://example.com/dataset/source-ds'

        result = self._build(ds)
        dataset_node = next(
            node for node in result['@graph'] if _node_has_type(node, 'dcat:Dataset')
        )

        self.assertEqual(
            dataset_node.get('dct:source'), {'@id': 'https://example.com/dataset/source-ds'}
        )

    def test_build_complete_jsonld_includes_catalogs_and_orphan_datasets(self) -> None:
        from shared.export import build_complete_jsonld

        catalog_dataset = self._make_dataset()
        catalog_dataset.catalog = None

        orphan_dataset = self._make_dataset()
        orphan_dataset.catalog = None
        orphan_dataset.name = 'orphan-ds'
        orphan_dataset.title = 'Orphan dataset'
        orphan_dataset.identifier = 'https://example.com/dataset/orphan-ds'

        catalog = ExportCatalog(
            app='warehouse',
            name='warehouse-cat',
            title='Warehouse Catalogue',
            description='Warehouse catalogue description',
            applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
            publisher=catalog_dataset.publisher,
            datasets=[catalog_dataset],
        )

        result = build_complete_jsonld([catalog], [orphan_dataset])
        ids = {node['@id'] for node in result['@graph'] if '@id' in node}
        catalog_nodes = [node for node in result['@graph'] if _node_has_type(node, 'dcat:Catalog')]

        self.assertEqual(len(catalog_nodes), 1)
        self.assertNotIn('@id', catalog_nodes[0])
        self.assertIn('https://example.com/dataset/test-ds', ids)
        self.assertIn('https://example.com/dataset/orphan-ds', ids)

    # ── RDF Turtle export ────────────────────────────────────────────────────

    def test_build_turtle_returns_valid_turtle(self) -> None:
        from shared.export import build_turtle

        turtle = build_turtle(self._make_dataset())
        self.assertIsInstance(turtle, str)
        self.assertIn('dcat:Dataset', turtle)

    def test_build_turtle_contains_dataset_title(self) -> None:
        from shared.export import build_turtle

        turtle = build_turtle(self._make_dataset())
        self.assertIn('Test dataset', turtle)

    # ── Multi-value URI field export ────────────────────────────────────────

    def _dataset_node(self, result: JsonLdDocument) -> JsonLdDatasetNode:
        return next(node for node in result['@graph'] if _node_has_type(node, 'dcat:Dataset'))

    def test_multiple_themes_exported_as_array(self) -> None:
        ds = self._make_dataset()
        ds.theme = 'http://example.com/theme/A;http://example.com/theme/B'
        node = self._dataset_node(self._build(ds))
        self.assertEqual(
            node.get('dcat:theme'),
            [{'@id': 'http://example.com/theme/A'}, {'@id': 'http://example.com/theme/B'}],
        )

    def test_single_theme_exported_as_single_ref(self) -> None:
        node = self._dataset_node(self._build())
        self.assertEqual(
            node.get('dcat:theme'),
            {'@id': 'http://publications.europa.eu/resource/authority/data-theme/HEAL'},
        )

    def test_multiple_health_categories_exported_as_array(self) -> None:
        ds = self._make_dataset()
        ds.health_category = 'http://example.com/cat/A;http://example.com/cat/B'
        node = self._dataset_node(self._build(ds))
        self.assertEqual(
            node.get('healthdcatap:healthCategory'),
            [{'@id': 'http://example.com/cat/A'}, {'@id': 'http://example.com/cat/B'}],
        )

    def test_multiple_applicable_legislations_exported_as_array(self) -> None:
        ds = self._make_dataset()
        ds.applicable_legislation = (
            'http://data.europa.eu/eli/reg/2016/679/oj;http://data.europa.eu/eli/reg/2022/868/oj'
        )
        node = self._dataset_node(self._build(ds))
        self.assertEqual(
            node.get('dcatap:applicableLegislation'),
            [
                {'@id': 'http://data.europa.eu/eli/reg/2016/679/oj'},
                {'@id': 'http://data.europa.eu/eli/reg/2022/868/oj'},
            ],
        )

    def test_distribution_multiple_applicable_legislations(self) -> None:
        ds = self._make_dataset()
        ds.distributions[
            0
        ].applicable_legislation = (
            'http://data.europa.eu/eli/reg/2016/679/oj;http://data.europa.eu/eli/reg/2022/868/oj'
        )
        dist = self._distribution_node(self._build(ds))
        self.assertEqual(
            dist.get('dcatap:applicableLegislation'),
            [
                {'@id': 'http://data.europa.eu/eli/reg/2016/679/oj'},
                {'@id': 'http://data.europa.eu/eli/reg/2022/868/oj'},
            ],
        )
