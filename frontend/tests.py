"""Tests for the frontend presentation layer."""

from collections import Counter
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from frontend.catalogue_helpers import dataset_to_dict
from frontend.detail_context import (
    build_chart_groups,
    build_dataset_dcat_rows,
    normalise_stat_charts,
    normalise_tables,
)
from frontend.filtering import FilterState, build_sidebar_context
from schema_registry.types import SchemaRegistryPayload
from shared.dtos import (
    ExportAgent,
    ExportCatalog,
    ExportColumn,
    ExportContactPoint,
    ExportDataset,
    ExportDistribution,
    ExportTable,
    UnifiedDataset,
    UnifiedDistribution,
    UnifiedStatChart,
    UnifiedTable,
    UnifiedTableColumn,
)


def _make_test_dataset(**overrides):
    """Create a UnifiedDataset with sensible defaults for frontend view tests."""
    defaults = {
        'app': 'fair_genomes',
        'name': 'test-dataset',
        'title': 'Test Dataset',
        'access_rights': 'PUBLIC',
        'keyword': 'genetics,biobank',
        'health_category': 'patient_data',
        'description': 'A test dataset',
    }
    defaults.update(overrides)
    dataset = UnifiedDataset(**defaults)
    dataset.distributions = [
        UnifiedDistribution(
            app=defaults['app'],
            name='test-dist',
            dataset_name=defaults['name'],
            title='Test Distribution',
        ),
    ]
    return dataset


def _mock_schema() -> SchemaRegistryPayload:
    return {
        'dct:title': {
            'prefix': 'dct',
            'label': 'Title',
            'local_name': 'title',
            'uri': 'http://purl.org/dc/terms/title',
            'requirement': 'mandatory',
            'cardinality': '1..*',
            'description': 'A name given to the Dataset.',
        },
        'dct:description': {
            'prefix': 'dct',
            'label': 'Description',
            'local_name': 'description',
            'uri': 'http://purl.org/dc/terms/description',
            'requirement': 'mandatory',
            'cardinality': '1..*',
            'description': 'A free-text account of the resource.',
        },
        'dct:accessRights': {
            'prefix': 'dct',
            'label': 'Access Rights',
            'local_name': 'accessRights',
            'uri': 'http://purl.org/dc/terms/accessRights',
            'requirement': 'mandatory',
            'cardinality': '1',
            'description': 'Information that indicates whether the resource is open data.',
        },
    }


def _make_test_export_dataset(**overrides):
    app = overrides.get('app', 'fair_genomes')
    contact_point = ExportContactPoint(
        app=app,
        identifier='cp-1',
        email='data@example.com',
        contact_page='https://example.com/contact',
    )
    publisher = ExportAgent(app=app, name='Test Publisher', contact_point=contact_point)
    hdab = ExportAgent(app=app, name='Test HDAB', contact_point=contact_point)
    defaults = {
        'app': app,
        'name': 'test-dataset',
        'title': 'Test Dataset',
        'description': 'A test dataset',
        'identifier': 'https://example.com/dataset/test-dataset',
        'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
        'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
        'publisher': publisher,
        'contact_point': contact_point,
        'access_rights': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
        'applicable_legislation': 'http://data.europa.eu/eli/reg/2022/868/oj',
        'health_category': 'http://healthdataportal.eu/ns/health#clinical',
        'hdab': hdab,
        'catalog': ExportCatalog(
            app=app,
            name='fg-cat',
            title='FAIR Genomes Catalogue',
            description='Test catalogue',
            applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
            publisher=publisher,
        ),
        'distributions': [
            ExportDistribution(
                app=app,
                name='test-dist',
                title='Test Distribution',
                access_url='https://example.com/distribution/test-dist',
                applicable_legislation='http://data.europa.eu/eli/reg/2022/868/oj',
                format='http://publications.europa.eu/resource/authority/file-type/XML',
            )
        ],
    }
    defaults.update(overrides)
    return ExportDataset(**defaults)


def _make_test_export_catalog(**overrides):
    publisher_cp = ExportContactPoint(
        app='fair_genomes',
        identifier='catalog-cp-1',
        email='catalog@example.com',
        contact_page='https://example.com/catalog-contact',
    )
    publisher = ExportAgent(
        app='fair_genomes', name='Catalog Publisher', contact_point=publisher_cp
    )
    dataset = _make_test_export_dataset(catalog=None)
    defaults = {
        'app': 'fair_genomes',
        'name': 'fg-cat',
        'title': 'FAIR Genomes Catalogue',
        'description': 'Test catalogue',
        'applicable_legislation': 'http://data.europa.eu/eli/reg/2022/868/oj',
        'publisher': publisher,
        'datasets': [dataset],
    }
    defaults.update(overrides)
    return ExportCatalog(**defaults)


_SERVICE_PATH = 'frontend.views.UnifiedCatalogService'
_DATASET_LOOKUP_PATH = 'frontend.views.get_cached_dataset_dict'


class CatalogueIndexViewTest(TestCase):
    """Tests for the main catalogue index view."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        django_cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='viewer', email='v@example.com', password='secret'
        )

    def test_requires_login(self):
        response = self.client.get(reverse('frontend:catalogue'))
        self.assertNotEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_returns_200_with_datasets(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [_make_test_dataset()]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Dataset')

    @patch(_SERVICE_PATH)
    def test_empty_catalogue(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = []
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))
        self.assertEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_text_search_filters(self, mock_cls):
        ds1 = _make_test_dataset(name='ds1', title='Alpha Dataset')
        ds2 = _make_test_dataset(name='ds2', title='Beta Dataset')
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [ds1, ds2]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'), {'q': 'Alpha'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Dataset')
        self.assertNotContains(response, 'Beta Dataset')


class DatasetDetailViewTest(TestCase):
    """Tests for the dataset detail view."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        django_cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='viewer2', email='v2@example.com', password='secret'
        )

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_SERVICE_PATH)
    def test_returns_200_for_existing_dataset(self, mock_cls, mock_dataset_lookup):
        dataset = _make_test_dataset()
        export_dataset = _make_test_export_dataset()
        mock_svc = mock_cls.return_value
        mock_svc.get_schema_json.return_value = _mock_schema()
        mock_svc.get_export_dataset.return_value = export_dataset

        from frontend.catalogue_helpers import dataset_to_dict

        mock_dataset_lookup.return_value = dataset_to_dict(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'fair_genomes', 'name': 'test-dataset'}
            )
        )
        self.assertEqual(response.status_code, 200)

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_SERVICE_PATH)
    def test_dataset_detail_includes_dataset_export_controls(self, mock_cls, mock_dataset_lookup):
        dataset = _make_test_dataset(app='warehouse', name='warehouse-dataset', title='Warehouse')
        dataset.distributions[0].name = 'warehouse-dist'
        export_dataset = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            title='Warehouse',
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='warehouse-dist',
                    title='Warehouse Distribution',
                    access_url='https://example.com/distribution/warehouse-dist',
                    tables=[
                        ExportTable(
                            name='encounter',
                            title='Encounter',
                            description='Encounter table',
                            columns=[
                                ExportColumn(
                                    name='patient_id',
                                    title='Patient ID',
                                    description='Primary patient identifier',
                                    datatype='string',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        mock_svc = mock_cls.return_value
        mock_svc.get_schema_json.return_value = _mock_schema()
        mock_svc.get_export_dataset.return_value = export_dataset

        from frontend.catalogue_helpers import dataset_to_dict

        mock_dataset_lookup.return_value = dataset_to_dict(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-export-action="download-jsonld"')
        self.assertContains(response, 'data-export-action="toggle-menu"')
        self.assertContains(response, 'jsonld-data')
        self.assertContains(
            response,
            reverse(
                'frontend:dataset_rdf_export',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'},
            ),
        )
        self.assertContains(response, 'encounter')
        self.assertContains(response, 'patient_id')
        self.assertNotContains(response, reverse('frontend_api:jsonld'))
        self.assertNotContains(response, reverse('frontend_api:rdf'))

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_SERVICE_PATH)
    def test_missing_dataset_raises_404(self, mock_cls, mock_dataset_lookup):
        """A non-existent dataset triggers Http404 in the view."""
        from django.http import Http404
        from django.test import RequestFactory

        from frontend.views import DatasetDetailView

        mock_cls.return_value.get_export_dataset.return_value = None
        mock_dataset_lookup.return_value = None

        self.client.force_login(self.user)
        with self.assertRaises(Http404):
            factory = RequestFactory()
            request = factory.get('/dataset/fair_genomes/nonexistent/')
            request.user = self.user
            request.session = self.client.session
            with patch(_SERVICE_PATH) as inner_service_mock:
                inner_service_mock.return_value.get_export_dataset.return_value = None
                with patch(_DATASET_LOOKUP_PATH, return_value=None):
                    DatasetDetailView.as_view()(request, app='fair_genomes', name='nonexistent')

    def test_dataset_specific_rdf_route_requires_login(self):
        response = self.client.get('/dataset/fair_genomes/test-dataset/rdf/')
        self.assertNotEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_dataset_specific_rdf_route_returns_tables_and_columns(self, mock_cls):
        export_dataset = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='warehouse-dist',
                    title='Warehouse Distribution',
                    access_url='https://example.com/distribution/warehouse-dist',
                    tables=[
                        ExportTable(
                            name='encounter',
                            title='Encounter',
                            description='Encounter table',
                            columns=[
                                ExportColumn(
                                    name='patient_id',
                                    title='Patient ID',
                                    description='Primary patient identifier',
                                    datatype='string',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        mock_cls.return_value.get_export_dataset.return_value = export_dataset

        self.client.force_login(self.user)
        response = self.client.get('/dataset/warehouse/warehouse-dataset/rdf/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/turtle; charset=utf-8')
        self.assertIn('encounter', response.content.decode())
        self.assertIn('patient_id', response.content.decode())


class MetadataApiViewTest(TestCase):
    """Tests for anonymous aggregate metadata API endpoints."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        django_cache.clear()

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_jsonld_endpoint_is_public(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])

        response = self.client.get(reverse('frontend_api:jsonld'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/ld+json; charset=utf-8')
        self.assertContains(response, 'FAIR Genomes Catalogue')
        self.assertContains(response, 'Test Dataset')

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_turtle_endpoint_is_public(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])

        response = self.client.get(reverse('frontend_api:rdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/turtle; charset=utf-8')
        self.assertIn('dcat:Catalog', response.content.decode())
        self.assertIn('dcat:Dataset', response.content.decode())

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_jsonld_endpoint_includes_orphan_datasets(self, mock_cls):
        mock_svc = mock_cls.return_value
        orphan_dataset = _make_test_export_dataset(
            name='orphan-dataset',
            identifier='https://example.com/dataset/orphan-dataset',
            catalog=None,
        )
        mock_svc.get_complete_export_catalogue.return_value = ([], [orphan_dataset])

        response = self.client.get(reverse('frontend_api:jsonld'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'orphan-dataset')


class SidebarContextHelperTest(SimpleTestCase):
    @patch('frontend.filtering.UnifiedCatalogService.build_column_counter')
    def test_build_sidebar_context_returns_typed_sidebar_payloads(self, mock_build_column_counter):
        warehouse_dataset = _make_test_dataset(
            app='warehouse',
            name='warehouse-dataset',
            keyword='oncology,patient',
            source='warehouse-ingest',
            custodian='AGENT_DATA_STEWARD',
            theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
        )
        warehouse_dataset.distributions[0].name = 'wh-dist'

        fair_genomes_dataset = _make_test_dataset(
            app='fair_genomes',
            name='fair-genomes-dataset',
            keyword='genomics',
        )
        fair_genomes_dataset.distributions[0].name = 'fg-dist'

        mock_build_column_counter.return_value = Counter({'patient_id': 2})

        context = build_sidebar_context(
            [dataset_to_dict(warehouse_dataset), dataset_to_dict(fair_genomes_dataset)],
            filter_state=FilterState(
                q='',
                status=set(),
                keywords={'patient'},
                source=set(),
                custodian={'AGENT_DATA_STEWARD'},
                health_category={'patient_data'},
                theme={'http://publications.europa.eu/resource/authority/data-theme/HEAL'},
                column={'patient_id'},
            ),
        )

        mock_build_column_counter.assert_called_once_with(
            ['wh-dist'],
            {'wh-dist': 'warehouse-dataset'},
        )

        patient_keyword = next(
            item for item in context['sidebar_keywords'] if item['value'] == 'patient'
        )
        custodian = next(
            item for item in context['sidebar_custodians'] if item['value'] == 'AGENT_DATA_STEWARD'
        )
        health_category = next(
            item for item in context['sidebar_health_categories'] if item['value'] == 'patient_data'
        )
        theme = next(
            item
            for item in context['sidebar_themes']
            if item['value'] == 'http://publications.europa.eu/resource/authority/data-theme/HEAL'
        )
        column = next(item for item in context['sidebar_columns'] if item['value'] == 'patient_id')

        self.assertEqual(patient_keyword['label'], 'patient')
        self.assertEqual(patient_keyword['count'], 1)
        self.assertTrue(patient_keyword['checked'])
        self.assertEqual(custodian['label'], 'DATA STEWARD')
        self.assertTrue(custodian['checked'])
        self.assertEqual(health_category['label'], 'Patient data')
        self.assertEqual(theme['label'], 'data-theme / HEAL')
        self.assertEqual(column['count'], 2)
        self.assertTrue(column['checked'])
        self.assertEqual(context['sidebar_counts']['ready'], 2)
        self.assertEqual(context['sidebar_counts']['raw'], 0)
        self.assertEqual(context['sidebar_counts']['unavailable'], 0)


class SchemaPayloadHelperTest(SimpleTestCase):
    def test_build_dataset_dcat_rows_uses_typed_schema_payload(self):
        dataset = dataset_to_dict(_make_test_dataset())

        rows = build_dataset_dcat_rows(_mock_schema(), dataset)

        self.assertEqual(
            rows,
            [
                ('dct:title', 'Title', 'Test Dataset'),
                ('dct:accessRights', 'Access Rights', 'PUBLIC'),
                ('dct:description', 'Description', 'A test dataset'),
            ],
        )


class ChartPayloadHelperTest(SimpleTestCase):
    def test_normalise_and_group_stat_charts(self):
        raw_charts: list[UnifiedStatChart] = [
            UnifiedStatChart(
                label='Instrument',
                table_name='sequencing',
                column_name='instrument',
                data={'MiSeq': 2, 'NovaSeq': 3},
            ),
            UnifiedStatChart(
                label='Kit',
                table_name='sequencing',
                column_name='kit',
                data={'A': 1},
            ),
        ]

        charts = normalise_stat_charts(raw_charts)
        chart_groups = build_chart_groups(charts)

        self.assertEqual(charts[0]['data']['MiSeq'], 2)
        self.assertNotIn('canvas_idx', charts[0])
        self.assertEqual(len(chart_groups), 1)
        self.assertEqual(chart_groups[0]['table_name'], 'sequencing')
        self.assertEqual(chart_groups[0]['charts'][0]['canvas_idx'], 1)
        self.assertEqual(chart_groups[0]['charts'][1]['canvas_idx'], 2)


class TablePayloadHelperTest(SimpleTestCase):
    def test_normalise_tables(self):
        raw_tables: list[UnifiedTable] = [
            UnifiedTable(
                name='encounter',
                title='Encounter',
                description='Encounter data',
                url='https://example.com/tables/encounter',
                columns=[
                    UnifiedTableColumn(
                        name='patient_id',
                        title='Patient ID',
                        description='Internal identifier',
                        datatype='string',
                        property_url='https://example.com/prop/patient-id',
                    )
                ],
            )
        ]

        tables = normalise_tables(raw_tables)

        self.assertEqual(tables[0]['name'], 'encounter')
        self.assertEqual(tables[0]['title'], 'Encounter')
        self.assertEqual(tables[0]['description'], 'Encounter data')
        self.assertEqual(tables[0]['url'], 'https://example.com/tables/encounter')
        self.assertEqual(tables[0]['columns'][0]['name'], 'patient_id')
        self.assertEqual(tables[0]['columns'][0]['datatype'], 'string')
        self.assertEqual(
            tables[0]['columns'][0]['property_url'],
            'https://example.com/prop/patient-id',
        )
