"""Tests for the frontend presentation layer."""

import json
from collections import Counter
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache as django_cache
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from frontend.models import CatalogueFilterDefinition
from frontend.presentation.filters import (
    FilterState,
    build_dataset_cards,
    build_sidebar_context,
    default_filter_definitions,
    load_enabled_filter_definitions,
)
from frontend.presentation.mapping import (
    build_chart_groups,
    build_dataset_dcat_rows,
    dataset_to_view_model,
    normalise_stat_charts,
    normalise_tables,
)
from frontend.presentation.types import CatalogueDistributionLookup
from frontend.templatetags.frontend_tags import active_filter_chips
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
from shared.export_types import ExportWarning, JsonLdExportResult, TurtleExportResult


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


def _make_distribution_lookup(dataset: UnifiedDataset) -> CatalogueDistributionLookup:
    dataset_view = dataset_to_view_model(dataset)
    distribution = dataset_view.distributions[0]
    return CatalogueDistributionLookup(distribution=distribution, dataset=dataset_view)


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
        'dcat:keyword': {
            'prefix': 'dcat',
            'label': 'Keyword',
            'local_name': 'keyword',
            'uri': 'http://www.w3.org/ns/dcat#keyword',
            'requirement': 'mandatory',
            'cardinality': '1..*',
            'description': 'A keyword or tag describing the Dataset.',
        },
        'dct:source': {
            'prefix': 'dct',
            'label': 'Source',
            'local_name': 'source',
            'uri': 'http://purl.org/dc/terms/source',
            'requirement': 'optional',
            'cardinality': '0..1',
            'description': 'Related source resource.',
        },
        'geodcatap:custodian': {
            'prefix': 'geodcatap',
            'label': 'Custodian',
            'local_name': 'custodian',
            'uri': 'http://data.europa.eu/930/custodian',
            'requirement': 'optional',
            'cardinality': '0..1',
            'description': 'Agent responsible for maintaining the Dataset.',
        },
        'healthdcatap:healthCategory': {
            'prefix': 'healthdcatap',
            'label': 'Health Category',
            'local_name': 'healthCategory',
            'uri': 'http://healthdcat-ap.example/healthCategory',
            'requirement': 'mandatory',
            'cardinality': '1..*',
            'description': 'Health category of the Dataset.',
        },
        'dcat:theme': {
            'prefix': 'dcat',
            'label': 'Theme',
            'local_name': 'theme',
            'uri': 'http://www.w3.org/ns/dcat#theme',
            'requirement': 'mandatory',
            'cardinality': '1..*',
            'description': 'Theme of the Dataset.',
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
        'health_category': 'http://13.81.34.152:1101/resource/authority/healthcategories/EHRS',
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


_VIEW_CONTEXT_SERVICE_PATH = 'frontend.presentation.context.UnifiedCatalogService'
_EXPORT_SERVICE_PATH = 'frontend.views.UnifiedCatalogService'
_DATASET_LOOKUP_PATH = 'frontend.presentation.context.get_cached_dataset'
_SCHEMA_LOOKUP_PATH = 'frontend.presentation.context.get_cached_schema_json'
_DISTRIBUTION_LOOKUP_PATH = 'frontend.presentation.context.get_cached_distribution_lookup'


class CatalogueFilterDefinitionModelTest(TestCase):
    databases = {'default'}

    def test_default_filter_definitions_are_seeded(self):
        field_names = set(CatalogueFilterDefinition.objects.values_list('field_name', flat=True))

        self.assertTrue(
            {'keywords', 'custodian', 'health_category', 'source', 'theme'} <= field_names
        )

    def test_reserved_field_names_are_rejected(self):
        definition = CatalogueFilterDefinition(
            field_name='q',
            label='Reserved',
            sort_order=1,
        )

        with self.assertRaises(ValidationError):
            definition.full_clean()

    def test_disabled_filters_are_not_loaded(self):
        CatalogueFilterDefinition.objects.filter(field_name='theme').update(is_enabled=False)

        definitions = load_enabled_filter_definitions(_mock_schema())

        self.assertNotIn('theme', {definition.field_name for definition in definitions})


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

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_returns_200_with_datasets(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [_make_test_dataset()]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Dataset')

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_empty_catalogue(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = []
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))
        self.assertEqual(response.status_code, 200)

    @override_settings(CATALOGUE_PAGE_SIZE=5)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_page_size_comes_from_settings(self, mock_cls):
        datasets = [
            _make_test_dataset(name=f'ds-{index}', title=f'Dataset {index}')
            for index in range(1, 8)
        ]
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = datasets
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.per_page, 5)
        self.assertEqual(len(response.context['page_obj'].object_list), 5)

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
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

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_text_search_matches_multi_value_metadata(self, mock_cls):
        ds1 = _make_test_dataset(
            name='ds1',
            title='Alpha Dataset',
            type='http://example.com/type/a;http://example.com/type/b',
            conforms_to='http://example.com/spec/a;http://example.com/spec/b',
            theme='http://example.com/theme/alpha',
            applicable_legislation='http://example.com/law/a;http://example.com/law/b',
        )
        ds2 = _make_test_dataset(name='ds2', title='Beta Dataset')
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [ds1, ds2]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('frontend:catalogue'), {'q': 'http://example.com/spec/b'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Dataset')
        self.assertNotContains(response, 'Beta Dataset')

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_catalogue_preview_renders_list_metadata_without_python_list_repr(self, mock_cls):
        dataset = _make_test_dataset(
            theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
            health_category='http://13.81.34.152:1101/resource/authority/healthcategories/EHRS',
        )
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [dataset]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'title="http://publications.europa.eu/resource/authority/data-theme/HEAL"',
        )
        self.assertNotContains(
            response,
            '[&#x27;http://publications.europa.eu/resource/authority/data-theme/HEAL&#x27;]',
            html=True,
        )
        self.assertNotContains(
            response,
            ('[&#x27;http://13.81.34.152:1101/resource/authority/healthcategories/EHRS&#x27;]'),
            html=True,
        )

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_sidebar_filter_titles_include_display_and_raw_value(self, mock_cls):
        dataset = _make_test_dataset(
            theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
        )
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [dataset]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'title="data-theme / HEAL | '
            'http://publications.europa.eu/resource/authority/data-theme/HEAL"',
        )

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_active_filter_chip_titles_include_full_value(self, mock_cls):
        theme_value = 'http://publications.europa.eu/resource/authority/data-theme/HEAL'
        dataset = _make_test_dataset(theme=theme_value)
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [dataset]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'), {'theme': theme_value})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'title="Theme: {theme_value}"')

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_admin_enabled_metadata_field_filters_without_template_change(self, mock_cls):
        CatalogueFilterDefinition.objects.create(
            field_name='access_rights',
            label='Access Rights',
            sort_order=5,
            is_enabled=True,
        )
        ds1 = _make_test_dataset(name='ds1', title='Public Dataset', access_rights='PUBLIC')
        ds2 = _make_test_dataset(name='ds2', title='Restricted Dataset', access_rights='RESTRICTED')
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [ds1, ds2]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'), {'access_rights': 'PUBLIC'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Public Dataset')
        self.assertNotContains(response, 'Restricted Dataset')

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_disabled_filter_is_not_rendered_or_used_for_preview(self, mock_cls):
        CatalogueFilterDefinition.objects.filter(field_name='theme').update(is_enabled=False)
        dataset = _make_test_dataset(
            theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
        )
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [dataset]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            'theme',
            {group.field_name for group in response.context['filter_groups']},
        )
        card = response.context['page_obj'].object_list[0]
        self.assertNotIn('theme', {row.field_name for row in card.preview_rows})

    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_preview_expand_is_disabled_when_no_filterable_metadata_is_enabled(self, mock_cls):
        CatalogueFilterDefinition.objects.update(is_enabled=False)
        dataset = _make_test_dataset()
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [dataset]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:catalogue'))

        self.assertEqual(response.status_code, 200)
        card = response.context['page_obj'].object_list[0]
        self.assertFalse(card.can_expand)
        self.assertEqual(card.preview_rows, [])


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
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_returns_200_for_existing_dataset(self, mock_cls, mock_dataset_lookup):
        dataset = _make_test_dataset()
        export_dataset = _make_test_export_dataset()
        mock_svc = mock_cls.return_value
        mock_svc.get_schema_json.return_value = _mock_schema()
        mock_svc.get_export_dataset.return_value = export_dataset
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'fair_genomes', 'name': 'test-dataset'}
            )
        )
        self.assertEqual(response.status_code, 200)

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
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
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                'frontend:dataset_jsonld_download',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'},
            ),
        )
        self.assertContains(response, 'x-data')
        self.assertContains(
            response,
            reverse(
                'frontend:dataset_rdf_export',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'},
            ),
        )
        self.assertNotContains(response, reverse('frontend_api:jsonld'))
        self.assertNotContains(response, reverse('frontend_api:rdf'))

    @patch('frontend.presentation.context.build_jsonld_result')
    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_dataset_detail_notifies_when_export_context_is_invalid(
        self,
        mock_cls,
        mock_dataset_lookup,
        mock_build_jsonld_result,
    ):
        dataset = _make_test_dataset(app='warehouse', name='warehouse-dataset', title='Warehouse')
        export_dataset = _make_test_export_dataset(app='warehouse', name='warehouse-dataset')
        mock_svc = mock_cls.return_value
        mock_svc.get_schema_json.return_value = _mock_schema()
        mock_svc.get_export_dataset.return_value = export_dataset
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)
        mock_build_jsonld_result.return_value = JsonLdExportResult(
            document={'@context': {}, '@graph': []},
            warnings=(
                ExportWarning(
                    code='missing_property',
                    message='Missing RDF property "title"',
                ),
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Export warnings')
        self.assertContains(response, 'Missing RDF property')
        self.assertContains(
            response,
            reverse(
                'frontend:dataset_jsonld_download',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'},
            ),
        )
        self.assertContains(
            response,
            reverse(
                'frontend:dataset_rdf_export',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'},
            ),
        )

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_dataset_detail_distribution_cards_do_not_render_inline_cart_buttons(
        self, mock_cls, mock_dataset_lookup
    ):
        dataset = _make_test_dataset(app='warehouse', name='warehouse-dataset', title='Warehouse')
        dataset.distributions[0].name = 'warehouse-dist'
        dataset.distributions[0].title = 'Warehouse Distribution'
        mock_cls.return_value.get_schema_json.return_value = _mock_schema()
        mock_cls.return_value.get_export_dataset.return_value = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            title='Warehouse',
        )
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'warehouse', 'name': 'warehouse-dataset'}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dist'},
            ),
        )
        self.assertNotContains(response, '"btn_style": "inline"')
        self.assertNotContains(response, 'name": "warehouse-dist"')

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_dataset_detail_renders_multi_value_metadata_as_separate_badges(
        self,
        mock_cls,
        mock_dataset_lookup,
    ):
        dataset = _make_test_dataset(
            type='http://example.com/type/a;http://example.com/type/b',
            conforms_to='http://example.com/spec/a;http://example.com/spec/b',
            applicable_legislation='http://example.com/law/a;http://example.com/law/b',
            theme='http://example.com/theme/a;http://example.com/theme/b',
            health_category='clinical;genomics',
        )
        export_dataset = _make_test_export_dataset()
        mock_svc = mock_cls.return_value
        mock_svc.get_export_dataset.return_value = export_dataset
        mock_svc.get_schema_json.return_value = {
            'dct:type': {
                'prefix': 'dct',
                'label': 'Type',
                'local_name': 'type',
                'uri': 'http://purl.org/dc/terms/type',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'The dataset type.',
            },
            'dct:conformsTo': {
                'prefix': 'dct',
                'label': 'Conforms To',
                'local_name': 'conformsTo',
                'uri': 'http://purl.org/dc/terms/conformsTo',
                'requirement': 'optional',
                'cardinality': '0..*',
                'description': 'A standard or profile the dataset conforms to.',
            },
            'dcatap:applicableLegislation': {
                'prefix': 'dcatap',
                'label': 'Applicable Legislation',
                'local_name': 'applicableLegislation',
                'uri': 'http://data.europa.eu/r5r/applicableLegislation',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'Applicable legislation.',
            },
            'dcat:theme': {
                'prefix': 'dcat',
                'label': 'Theme',
                'local_name': 'theme',
                'uri': 'http://www.w3.org/ns/dcat#theme',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'Theme.',
            },
            'healthdcatap:healthCategory': {
                'prefix': 'healthdcatap',
                'label': 'Health Category',
                'local_name': 'healthCategory',
                'uri': 'https://healthdcat-ap.github.io/#healthCategory',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'Health category.',
            },
        }
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:dataset_detail', kwargs={'app': 'fair_genomes', 'name': 'test-dataset'}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="http://example.com/type/a"')
        self.assertContains(response, 'title="http://example.com/type/b"')
        self.assertContains(response, 'title="http://example.com/spec/a"')
        self.assertContains(response, 'title="http://example.com/spec/b"')
        self.assertContains(response, 'title="http://example.com/law/a"')
        self.assertContains(response, 'title="http://example.com/theme/a"')
        self.assertContains(response, 'title="clinical"')
        self.assertNotContains(
            response,
            '[&#x27;http://example.com/type/a&#x27;, &#x27;http://example.com/type/b&#x27;]',
            html=True,
        )

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
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
            with patch(_VIEW_CONTEXT_SERVICE_PATH) as inner_service_mock:
                inner_service_mock.return_value.get_export_dataset.return_value = None
                with patch(_DATASET_LOOKUP_PATH, return_value=None):
                    DatasetDetailView.as_view()(request, app='fair_genomes', name='nonexistent')

    def test_dataset_specific_rdf_route_requires_login(self):
        response = self.client.get('/dataset/fair_genomes/test-dataset/rdf/')
        self.assertNotEqual(response.status_code, 200)

    @patch(_EXPORT_SERVICE_PATH)
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
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '0')
        self.assertIn('encounter', response.content.decode())
        self.assertIn('patient_id', response.content.decode())

    @patch('frontend.views.build_turtle_result')
    @patch(_EXPORT_SERVICE_PATH)
    def test_dataset_specific_rdf_route_notifies_when_export_is_invalid(
        self,
        mock_cls,
        mock_build_turtle_result,
    ):
        export_dataset = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='warehouse-dist',
                    access_url='https://example.com/distribution/warehouse-dist',
                )
            ],
        )
        mock_cls.return_value.get_export_dataset.return_value = export_dataset
        mock_build_turtle_result.return_value = TurtleExportResult(
            content='@prefix dcat: <http://www.w3.org/ns/dcat#> .\n',
            warnings=(
                ExportWarning(
                    code='missing_term',
                    message='Missing RDF term "csvw:table"',
                ),
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get('/dataset/warehouse/warehouse-dataset/rdf/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/turtle; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '1')
        self.assertIn('Missing RDF term', response['X-Metadata-Export-Warnings'])
        self.assertNotIn('Missing RDF term', response.content.decode())

    @patch(_EXPORT_SERVICE_PATH)
    def test_dataset_specific_jsonld_route_returns_serialized_json_document(self, mock_cls):
        export_dataset = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            title='Warehouse',
            identifier='https://example.com/dataset/warehouse-dataset',
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='warehouse-dist',
                    title='Warehouse Distribution',
                    access_url='https://example.com/distribution/warehouse-dist',
                )
            ],
        )
        mock_cls.return_value.get_export_dataset.return_value = export_dataset

        self.client.force_login(self.user)
        response = self.client.get('/dataset/warehouse/warehouse-dataset/jsonld/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/ld+json; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '0')
        payload = json.loads(response.content.decode())
        self.assertEqual(set(payload.keys()), {'@context', '@graph'})
        self.assertIsInstance(payload['@graph'], list)
        self.assertNotEqual(response.content.decode(), '@context@graph')
        self.assertIn('Warehouse Distribution', response.content.decode())

    @patch('frontend.views.build_jsonld_result')
    @patch(_EXPORT_SERVICE_PATH)
    def test_dataset_specific_jsonld_route_notifies_when_export_is_invalid(
        self,
        mock_cls,
        mock_build_jsonld_result,
    ):
        export_dataset = _make_test_export_dataset(
            app='warehouse',
            name='warehouse-dataset',
            distributions=[
                ExportDistribution(
                    app='warehouse',
                    name='warehouse-dist',
                    access_url='https://example.com/distribution/warehouse-dist',
                )
            ],
        )
        mock_cls.return_value.get_export_dataset.return_value = export_dataset
        mock_build_jsonld_result.return_value = JsonLdExportResult(
            document={'@context': {}, '@graph': []},
            warnings=(
                ExportWarning(
                    code='missing_class',
                    message='Missing RDF class "Dataset"',
                ),
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get('/dataset/warehouse/warehouse-dataset/jsonld/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/ld+json; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '1')
        self.assertIn('Missing RDF class', response['X-Metadata-Export-Warnings'])
        self.assertNotIn('Missing RDF class', response.content.decode())

    @patch(_DATASET_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_dataset_without_distributions_raises_404(self, mock_cls, mock_dataset_lookup):
        from django.http import Http404
        from django.test import RequestFactory

        from frontend.views import DatasetDetailView

        dataset = _make_test_dataset()
        dataset.distributions = []
        export_dataset = _make_test_export_dataset(distributions=[])

        mock_cls.return_value.get_export_dataset.return_value = export_dataset
        mock_dataset_lookup.return_value = dataset_to_view_model(dataset)

        factory = RequestFactory()
        request = factory.get('/dataset/fair_genomes/test-dataset/')
        request.user = self.user
        request.session = self.client.session

        with self.assertRaises(Http404):
            DatasetDetailView.as_view()(request, app='fair_genomes', name='test-dataset')


class DistributionDetailViewTest(TestCase):
    """Tests for the distribution detail view."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        django_cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='viewer-dist', email='vd@example.com', password='secret'
        )

    @patch(_SCHEMA_LOOKUP_PATH)
    @patch(_DISTRIBUTION_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_distribution_detail_requests_tables_and_charts(
        self,
        mock_cls,
        mock_get_distribution_lookup,
        mock_get_schema,
    ):
        dataset = _make_test_dataset(app='warehouse', name='warehouse-dataset', title='Warehouse')
        dataset.distributions[0].name = 'warehouse-dist'
        dataset.distributions[0].title = 'Warehouse Distribution'

        mock_get_distribution_lookup.return_value = _make_distribution_lookup(dataset)
        mock_get_schema.return_value = _mock_schema()

        mock_svc = mock_cls.return_value
        mock_svc.get_tables_with_columns.return_value = [
            UnifiedTable(
                name='encounter',
                title='Encounter',
                description='Encounter table',
                url='https://example.com/tables/encounter',
                columns=[
                    UnifiedTableColumn(
                        name='patient_id',
                        title='Patient ID',
                        description='Patient identifier',
                        datatype='string',
                        property_url='https://example.com/props/patient-id',
                    )
                ],
            )
        ]
        mock_svc.get_stat_charts.return_value = [
            UnifiedStatChart(
                label='Instrument',
                table_name='sequencing',
                column_name='sequencinginstrumentmodel',
                data={'MiSeq': 10, 'NovaSeq': 5},
            )
        ]

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dist'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Encounter')
        self.assertContains(response, 'Instrument')
        mock_svc.get_tables_with_columns.assert_called_once_with('warehouse', 'warehouse-dist')
        mock_svc.get_stat_charts.assert_called_once_with('warehouse', 'warehouse-dist')

    @patch(_SCHEMA_LOOKUP_PATH)
    @patch(_DISTRIBUTION_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_distribution_detail_handles_third_app_without_special_branches(
        self,
        mock_cls,
        mock_get_distribution_lookup,
        mock_get_schema,
    ):
        dataset = _make_test_dataset(app='third_source', name='third-dataset', title='Third Source')
        dataset.distributions[0].name = 'third-dist'
        dataset.distributions[0].title = 'Third Distribution'

        mock_get_distribution_lookup.return_value = _make_distribution_lookup(dataset)
        mock_get_schema.return_value = _mock_schema()

        mock_svc = mock_cls.return_value
        mock_svc.get_tables_with_columns.return_value = []
        mock_svc.get_stat_charts.return_value = []

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'third_source', 'name': 'third-dist'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Third Distribution')
        mock_svc.get_tables_with_columns.assert_called_once_with('third_source', 'third-dist')
        mock_svc.get_stat_charts.assert_called_once_with('third_source', 'third-dist')

    @patch(_SCHEMA_LOOKUP_PATH)
    @patch(_DISTRIBUTION_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_distribution_detail_cart_button_targets_parent_dataset(
        self,
        mock_cls,
        mock_get_distribution_lookup,
        mock_get_schema,
    ):
        dataset = _make_test_dataset(app='warehouse', name='warehouse-dataset', title='Warehouse')
        dataset.distributions[0].name = 'warehouse-dist'
        dataset.distributions[0].title = 'Warehouse Distribution'

        mock_get_distribution_lookup.return_value = _make_distribution_lookup(dataset)
        mock_get_schema.return_value = _mock_schema()
        mock_cls.return_value.get_tables_with_columns.return_value = []
        mock_cls.return_value.get_stat_charts.return_value = []

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'warehouse', 'name': 'warehouse-dist'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"name": "warehouse-dataset"')
        self.assertContains(response, '"title": "Warehouse"')
        self.assertNotContains(response, '"title": "Warehouse Distribution"')
        self.assertContains(
            response, '<span class="font-medium text-txt-muted">Warehouse</span>', html=True
        )

    @patch(_SCHEMA_LOOKUP_PATH)
    @patch(_DISTRIBUTION_LOOKUP_PATH)
    @patch(_VIEW_CONTEXT_SERVICE_PATH)
    def test_distribution_detail_renders_multi_value_metadata_as_separate_badges(
        self,
        mock_cls,
        mock_get_distribution_lookup,
        mock_get_schema,
    ):
        dataset = _make_test_dataset()
        dataset.distributions[0].name = 'test-dist'
        dataset.distributions[0].title = 'Test Distribution'
        dataset.distributions[
            0
        ].conforms_to = 'http://example.com/profile/a;http://example.com/profile/b'
        dataset.distributions[
            0
        ].applicable_legislation = 'http://example.com/law/a;http://example.com/law/b'

        mock_get_distribution_lookup.return_value = _make_distribution_lookup(dataset)
        mock_get_schema.return_value = {
            'dct:conformsTo': {
                'prefix': 'dct',
                'label': 'Conforms To',
                'local_name': 'conformsTo',
                'uri': 'http://purl.org/dc/terms/conformsTo',
                'requirement': 'optional',
                'cardinality': '0..*',
                'description': 'A standard or profile the distribution conforms to.',
            },
            'dcatap:applicableLegislation': {
                'prefix': 'dcatap',
                'label': 'Applicable Legislation',
                'local_name': 'applicableLegislation',
                'uri': 'http://data.europa.eu/r5r/applicableLegislation',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'Applicable legislation.',
            },
        }
        mock_cls.return_value.get_tables_with_columns.return_value = []
        mock_cls.return_value.get_stat_charts.return_value = []

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'fair_genomes', 'name': 'test-dist'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="http://example.com/profile/a"')
        self.assertContains(response, 'title="http://example.com/profile/b"')
        self.assertContains(response, 'title="http://example.com/law/a"')
        self.assertContains(response, 'title="http://example.com/law/b"')
        self.assertNotContains(
            response,
            (
                '[&#x27;http://example.com/profile/a&#x27;, '
                '&#x27;http://example.com/profile/b&#x27;]'
            ),
            html=True,
        )

    @patch(_DISTRIBUTION_LOOKUP_PATH, return_value=None)
    def test_missing_distribution_returns_404(self, _mock_get_distribution_lookup):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'frontend:distribution_detail',
                kwargs={'app': 'fair_genomes', 'name': 'missing-dist'},
            )
        )

        self.assertEqual(response.status_code, 404)


class MetadataApiViewTest(TestCase):
    """Tests for authenticated aggregate metadata API endpoints."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        django_cache.clear()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='api_viewer', email='api@example.com', password='secret'
        )

    def test_jsonld_endpoint_requires_auth(self):
        response = self.client.get(reverse('frontend_api:jsonld'))
        self.assertEqual(response.status_code, 401)

    def test_turtle_endpoint_requires_auth(self):
        response = self.client.get(reverse('frontend_api:rdf'))
        self.assertEqual(response.status_code, 401)

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_jsonld_endpoint_returns_data_when_authenticated(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend_api:jsonld'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/ld+json; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '0')
        self.assertContains(response, 'FAIR Genomes Catalogue')
        self.assertContains(response, 'Test Dataset')

    @patch('frontend.api_views.build_complete_jsonld_result')
    @patch('frontend.api_views.UnifiedCatalogService')
    def test_jsonld_endpoint_notifies_when_export_is_invalid(
        self,
        mock_cls,
        mock_build_complete_jsonld_result,
    ):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])
        mock_build_complete_jsonld_result.return_value = JsonLdExportResult(
            document={'@context': {}, '@graph': []},
            warnings=(
                ExportWarning(
                    code='missing_property',
                    message='Missing RDF property "title"',
                ),
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend_api:jsonld'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/ld+json; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '1')
        self.assertIn('Missing RDF property', response['X-Metadata-Export-Warnings'])
        self.assertNotIn('Missing RDF property', response.content.decode())

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_turtle_endpoint_returns_data_when_authenticated(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend_api:rdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/turtle; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '0')
        self.assertIn('dcat:Catalog', response.content.decode())
        self.assertIn('dcat:Dataset', response.content.decode())

    @patch('frontend.api_views.build_complete_turtle_result')
    @patch('frontend.api_views.UnifiedCatalogService')
    def test_turtle_endpoint_notifies_when_export_is_invalid(
        self,
        mock_cls,
        mock_build_complete_turtle_result,
    ):
        mock_svc = mock_cls.return_value
        mock_svc.get_complete_export_catalogue.return_value = ([_make_test_export_catalog()], [])
        mock_build_complete_turtle_result.return_value = TurtleExportResult(
            content='@prefix dcat: <http://www.w3.org/ns/dcat#> .\n',
            warnings=(
                ExportWarning(
                    code='missing_class',
                    message='Missing RDF class "Dataset"',
                ),
            ),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend_api:rdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/turtle; charset=utf-8')
        self.assertEqual(response['X-Metadata-Export-Warning-Count'], '1')
        self.assertIn('Missing RDF class', response['X-Metadata-Export-Warnings'])
        self.assertNotIn('Missing RDF class', response.content.decode())

    @patch('frontend.api_views.UnifiedCatalogService')
    def test_jsonld_endpoint_includes_orphan_datasets(self, mock_cls):
        mock_svc = mock_cls.return_value
        orphan_dataset = _make_test_export_dataset(
            name='orphan-dataset',
            identifier='https://example.com/dataset/orphan-dataset',
            catalog=None,
        )
        mock_svc.get_complete_export_catalogue.return_value = ([], [orphan_dataset])

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend_api:jsonld'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'orphan-dataset')


class SidebarContextHelperTest(SimpleTestCase):
    def test_build_dataset_cards_uses_enabled_filter_definitions_for_preview(self):
        schema = _mock_schema()
        definitions = default_filter_definitions(schema)
        dataset = dataset_to_view_model(
            _make_test_dataset(
                keyword='genetics,biobank',
                custodian='AGENT_DATA_STEWARD',
                theme='http://publications.europa.eu/resource/authority/data-theme/HEAL',
            )
        )

        cards = build_dataset_cards([dataset], schema_json=schema, filter_definitions=definitions)

        self.assertTrue(cards[0].can_expand)
        self.assertEqual(
            {row.field_name for row in cards[0].preview_rows},
            {'keywords', 'custodian', 'health_category', 'theme'},
        )

    @patch('frontend.presentation.filters.UnifiedCatalogService.build_column_counter')
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
        schema = _mock_schema()
        filter_definitions = default_filter_definitions(schema)
        filter_state = FilterState.from_query_params(
            QueryDict(
                'keywords=patient&custodian=AGENT_DATA_STEWARD&health_category=patient_data'
                '&theme=http://publications.europa.eu/resource/authority/data-theme/HEAL'
                '&column=patient_id'
            ),
            filter_definitions=filter_definitions,
        )

        context = build_sidebar_context(
            [
                dataset_to_view_model(warehouse_dataset),
                dataset_to_view_model(fair_genomes_dataset),
            ],
            filter_state=filter_state,
            schema_json=schema,
            filter_definitions=filter_definitions,
        )

        mock_build_column_counter.assert_called_once_with(
            ['wh-dist'],
            {'wh-dist': 'warehouse-dataset'},
        )

        filter_groups = {group.field_name: group for group in context.filter_groups}
        patient_keyword = next(
            item for item in filter_groups['keywords'].items if item.value == 'patient'
        )
        custodian = next(
            item for item in filter_groups['custodian'].items if item.value == 'AGENT_DATA_STEWARD'
        )
        health_category = next(
            item for item in filter_groups['health_category'].items if item.value == 'patient_data'
        )
        theme = next(
            item
            for item in filter_groups['theme'].items
            if item.value == 'http://publications.europa.eu/resource/authority/data-theme/HEAL'
        )
        column = next(item for item in context.sidebar_columns if item.value == 'patient_id')

        self.assertEqual(patient_keyword.label, 'patient')
        self.assertEqual(patient_keyword.count, 1)
        self.assertTrue(patient_keyword.checked)
        self.assertEqual(custodian.label, 'DATA STEWARD')
        self.assertTrue(custodian.checked)
        self.assertEqual(health_category.label, 'Patient data')
        self.assertEqual(theme.label, 'data-theme / HEAL')
        self.assertEqual(column.count, 2)
        self.assertTrue(column.checked)
        self.assertEqual(context.sidebar_counts.ready, 2)
        self.assertEqual(context.sidebar_counts.raw, 0)
        self.assertEqual(context.sidebar_counts.unavailable, 0)


class FilterStateParsingTest(SimpleTestCase):
    def test_from_query_params_parses_multiselect_filters(self):
        query_params = QueryDict(
            'q=Alpha&status=ready&status=raw&source=warehouse&theme=http://example.com/theme'
            '&column=patient_id'
        )

        state = FilterState.from_query_params(query_params)

        self.assertEqual(state.q, 'Alpha')
        self.assertEqual(state.status, {'ready', 'raw'})
        self.assertEqual(state.source, {'warehouse'})
        self.assertEqual(state.theme, {'http://example.com/theme'})
        self.assertEqual(state.column, {'patient_id'})


class ActiveFilterChipHelperTest(SimpleTestCase):
    def test_builds_remove_urls_without_losing_other_filters(self):
        query_params = QueryDict(
            'q=Alpha&theme=http://example.com/theme&theme=http://example.com/other&page=3'
        )
        filter_params = FilterState.from_query_params(query_params)

        chips = active_filter_chips(filter_params, query_params, '/catalogue/')

        self.assertEqual(len(chips), 3)
        theme_chip = next(chip for chip in chips if chip.title.endswith('http://example.com/theme'))
        self.assertIn('page=1', theme_chip.remove_url)
        self.assertIn('q=Alpha', theme_chip.remove_url)
        self.assertIn('theme=http%3A%2F%2Fexample.com%2Fother', theme_chip.remove_url)
        self.assertNotIn('theme=http%3A%2F%2Fexample.com%2Ftheme', theme_chip.remove_url)


class AuthGuardHelperTest(SimpleTestCase):
    def test_require_auth_rejects_anonymous_requests(self):
        from django.test import RequestFactory

        from frontend.api_views import _require_auth

        request = RequestFactory().get('/api/jsonld')
        request.user = AnonymousUser()

        response = _require_auth(request)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)

    def test_require_auth_allows_authenticated_requests(self):
        from django.test import RequestFactory

        from frontend.api_views import _require_auth

        request = RequestFactory().get('/api/jsonld')
        request.user = type('UserStub', (), {'is_authenticated': True})()

        self.assertIsNone(_require_auth(request))


class SchemaPayloadHelperTest(SimpleTestCase):
    def test_build_dataset_dcat_rows_uses_typed_schema_payload(self):
        dataset = dataset_to_view_model(_make_test_dataset())
        schema = {
            'dct:title': _mock_schema()['dct:title'],
            'dct:accessRights': _mock_schema()['dct:accessRights'],
        }

        rows = build_dataset_dcat_rows(schema, dataset)

        self.assertEqual(
            rows,
            [
                ('dct:title', 'Title', 'Test Dataset'),
                ('dct:accessRights', 'Access Rights', 'PUBLIC'),
            ],
        )

    def test_build_dataset_dcat_rows_preserves_identifier_and_type_fields(self):
        dataset = dataset_to_view_model(
            _make_test_dataset(
                identifier='https://example.com/datasets/test-dataset',
                type=(
                    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL;'
                    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE'
                ),
            )
        )
        schema = {
            'dct:identifier': {
                'prefix': 'dct',
                'label': 'Identifier',
                'local_name': 'identifier',
                'uri': 'http://purl.org/dc/terms/identifier',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'A unique identifier for the Dataset.',
            },
            'dct:type': {
                'prefix': 'dct',
                'label': 'Type',
                'local_name': 'type',
                'uri': 'http://purl.org/dc/terms/type',
                'requirement': 'mandatory',
                'cardinality': '1..*',
                'description': 'The dataset type.',
            },
        }

        rows = build_dataset_dcat_rows(schema, dataset)

        self.assertIn(
            ('dct:identifier', 'Identifier', 'https://example.com/datasets/test-dataset'),
            rows,
        )
        self.assertIn(
            (
                'dct:type',
                'Type',
                [
                    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                ],
            ),
            rows,
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

        self.assertEqual(charts[0].data['MiSeq'], 2)
        self.assertIsNone(charts[0].canvas_idx)
        self.assertEqual(len(chart_groups), 1)
        self.assertEqual(chart_groups[0].table_name, 'sequencing')
        self.assertEqual(chart_groups[0].charts[0].canvas_idx, 1)
        self.assertEqual(chart_groups[0].charts[1].canvas_idx, 2)


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

        self.assertEqual(tables[0].name, 'encounter')
        self.assertEqual(tables[0].title, 'Encounter')
        self.assertEqual(tables[0].description, 'Encounter data')
        self.assertEqual(tables[0].url, 'https://example.com/tables/encounter')
        self.assertEqual(tables[0].columns[0].name, 'patient_id')
        self.assertEqual(tables[0].columns[0].datatype, 'string')
        self.assertEqual(
            tables[0].columns[0].property_url,
            'https://example.com/prop/patient-id',
        )


class ParseMultiValuesTest(SimpleTestCase):
    """Tests for the semicolon-separated multi-value parser."""

    def test_splits_semicolons(self):
        from shared.services import parse_multi_values

        self.assertEqual(
            parse_multi_values('http://a;http://b;http://c'),
            ['http://a', 'http://b', 'http://c'],
        )

    def test_strips_whitespace(self):
        from shared.services import parse_multi_values

        self.assertEqual(
            parse_multi_values(' http://a ; http://b '),
            ['http://a', 'http://b'],
        )

    def test_empty_string_returns_empty_list(self):
        from shared.services import parse_multi_values

        self.assertEqual(parse_multi_values(''), [])

    def test_none_returns_empty_list(self):
        from shared.services import parse_multi_values

        self.assertEqual(parse_multi_values(None), [])

    def test_single_value(self):
        from shared.services import parse_multi_values

        self.assertEqual(parse_multi_values('http://only'), ['http://only'])

    def test_deduplicates_repeated_values(self):
        from shared.services import parse_multi_values

        self.assertEqual(
            parse_multi_values('http://a; http://b; http://a; http://b'),
            ['http://a', 'http://b'],
        )


class MultiValueMapperTest(SimpleTestCase):
    """Tests that dataset_to_dict pre-splits multi-value URI fields into lists."""

    def test_theme_split_into_list(self):
        ds = _make_test_dataset(theme='http://a;http://b')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.theme, ['http://a', 'http://b'])

    def test_theme_deduplicates_repeated_values(self):
        ds = _make_test_dataset(theme='http://a;http://b;http://a')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.theme, ['http://a', 'http://b'])

    def test_applicable_legislation_split_into_list(self):
        ds = _make_test_dataset(applicable_legislation='http://x;http://y')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.applicable_legislation, ['http://x', 'http://y'])

    def test_type_split_into_list(self):
        ds = _make_test_dataset(type='http://a;http://b')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.type, ['http://a', 'http://b'])

    def test_conforms_to_split_into_list(self):
        ds = _make_test_dataset(conforms_to='http://spec/a;http://spec/b')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.conforms_to, ['http://spec/a', 'http://spec/b'])

    def test_health_category_split_into_list(self):
        ds = _make_test_dataset(health_category='cat_a;cat_b')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.health_category, ['cat_a', 'cat_b'])

    def test_single_value_is_single_element_list(self):
        ds = _make_test_dataset(health_category='patient_data')
        result = dataset_to_view_model(ds)
        self.assertEqual(result.health_category, ['patient_data'])

    def test_empty_value_is_empty_list(self):
        ds = _make_test_dataset(theme=None)
        result = dataset_to_view_model(ds)
        self.assertEqual(result.theme, [])

    def test_distribution_conforms_to_split_into_list(self):
        ds = _make_test_dataset()
        ds.distributions = [
            UnifiedDistribution(
                app='fair_genomes',
                name='test-dist',
                dataset_name='test-dataset',
                title='Test Distribution',
                conforms_to='http://profile/a;http://profile/b',
            ),
        ]
        result = dataset_to_view_model(ds)
        self.assertEqual(
            result.distributions[0].conforms_to, ['http://profile/a', 'http://profile/b']
        )
