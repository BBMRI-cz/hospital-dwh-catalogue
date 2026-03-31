"""
Tests for the warehouse application â€” Local Metadata HealthDCAT-AP Profile.

All warehouse models are managed=False (pre-existing metadata_db tables).
Tests verify model structure, __str__, and Meta without DB writes.
View tests mock UnifiedCatalogService to avoid requiring real metadata_db data.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache as django_cache
from django.test import TestCase
from django.urls import reverse

from shared.dtos import UnifiedDataset, UnifiedDistribution

from .models import Agent, Catalog, Column, ContactPoint, Dataset, Distribution, Table


class ContactPointModelTest(TestCase):
    """Tests for the ContactPoint model."""

    databases = {'default', 'auth_db'}

    def test_str_with_email(self):
        obj = ContactPoint(email='test@example.com')
        self.assertEqual(str(obj), 'test@example.com')

    def test_str_with_page(self):
        obj = ContactPoint(contact_page='https://example.com/contact')
        self.assertEqual(str(obj), 'https://example.com/contact')

    def test_meta_managed_false(self):
        self.assertFalse(ContactPoint._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(ContactPoint._meta.db_table, 'metadata"."lm_contact_point')


class AgentModelTest(TestCase):
    """Tests for the Agent model."""

    databases = {'default', 'auth_db'}

    def test_str(self):
        obj = Agent(name='Hospital Publisher')
        self.assertEqual(str(obj), 'Hospital Publisher')

    def test_meta_managed_false(self):
        self.assertFalse(Agent._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Agent._meta.db_table, 'metadata"."lm_agent')


class CatalogModelTest(TestCase):
    """Tests for the Catalog model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Catalog(name='cat1', title='Hospital Catalogue')
        self.assertEqual(str(obj), 'Hospital Catalogue')

    def test_str_fallback_to_name(self):
        obj = Catalog(name='cat1', title='')
        self.assertEqual(str(obj), 'cat1')

    def test_meta_managed_false(self):
        self.assertFalse(Catalog._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Catalog._meta.db_table, 'metadata"."lm_catalog')

    def test_mandatory_fields_present(self):
        """title and description are mandatory per HealthDCAT-AP v6."""
        for field_name in ('title', 'description', 'applicable_legislation'):
            field = Catalog._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class DatasetModelTest(TestCase):
    """Tests for the Dataset model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Dataset(name='ds1', title='Patient Dataset')
        self.assertEqual(str(obj), 'Patient Dataset')

    def test_str_fallback_to_name(self):
        obj = Dataset(name='ds1', title='')
        self.assertEqual(str(obj), 'ds1')

    def test_meta_managed_false(self):
        self.assertFalse(Dataset._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Dataset._meta.db_table, 'metadata"."lm_dataset')

    def test_mandatory_fields_present(self):
        """Mandatory HealthDCAT-AP v6 fields must not allow blank."""
        for field_name in (
            'access_rights',
            'applicable_legislation',
            'health_category',
            'title',
            'description',
        ):
            field = Dataset._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class DistributionModelTest(TestCase):
    """Tests for the Distribution model."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Distribution(name='dist1', title='CSV Export')
        self.assertEqual(str(obj), 'CSV Export')

    def test_str_fallback_to_name(self):
        obj = Distribution(name='dist1', title='')
        self.assertEqual(str(obj), 'dist1')

    def test_db_layer_field_nullable(self):
        field = Distribution._meta.get_field('db_layer')
        self.assertTrue(field.null)
        self.assertTrue(field.blank)

    def test_meta_managed_false(self):
        self.assertFalse(Distribution._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Distribution._meta.db_table, 'metadata"."lm_distribution')

    def test_mandatory_fields_present(self):
        for field_name in ('access_url', 'applicable_legislation'):
            field = Distribution._meta.get_field(field_name)
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')


class TableModelTest(TestCase):
    """Tests for the Table model (csvw:Table)."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Table(name='TBL_PAT_RAW', title='Raw patient table')
        self.assertEqual(str(obj), 'Raw patient table')

    def test_str_fallback_to_name(self):
        obj = Table(name='TBL_PAT_RAW', title=None)
        self.assertEqual(str(obj), 'TBL_PAT_RAW')

    def test_meta_managed_false(self):
        self.assertFalse(Table._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Table._meta.db_table, 'metadata"."lm_table')

    def test_meta_ordering(self):
        self.assertEqual(Table._meta.ordering, ['name'])

    def test_url_mandatory(self):
        field = Table._meta.get_field('url')
        self.assertFalse(field.null)
        self.assertFalse(field.blank)


class ColumnModelTest(TestCase):
    """Tests for the Column model (csvw:Column)."""

    databases = {'default', 'auth_db'}

    def test_str_with_title(self):
        obj = Column(name='COL_PAT_ID', title='ID pacienta')
        self.assertEqual(str(obj), 'ID pacienta')

    def test_str_fallback_to_name(self):
        obj = Column(name='COL_PAT_ID', title='')
        self.assertEqual(str(obj), 'COL_PAT_ID')

    def test_meta_managed_false(self):
        self.assertFalse(Column._meta.managed)

    def test_meta_db_table(self):
        self.assertEqual(Column._meta.db_table, 'metadata"."lm_column')

    def test_meta_ordering(self):
        self.assertEqual(Column._meta.ordering, ['var_order', 'name'])

    def test_mandatory_fields_not_nullable(self):
        """title, description, datatype are mandatory and must not allow null/blank."""
        for field_name in ('title', 'description', 'datatype'):
            field = Column._meta.get_field(field_name)
            self.assertFalse(
                getattr(field, 'null', False), msg=f'{field_name} should not be null=True'
            )
            self.assertFalse(field.blank, msg=f'{field_name} should have blank=False')

    def test_optional_fields_nullable(self):
        """All metadata helper fields must be nullable."""
        for field_name in (
            'property_url',
            'var_order',
            'key_db',
            'type_r',
            'definition_ddl',
            'definition_pk_pom1',
            'definition_pk_pom2',
            'definition_pk',
        ):
            field = Column._meta.get_field(field_name)
            self.assertTrue(field.null, msg=f'{field_name} should allow null')
            self.assertTrue(field.blank, msg=f'{field_name} should allow blank')


# ── View tests ────────────────────────────────────────────────────────────────


def _make_test_dataset(**overrides):
    """Create a UnifiedDataset with sensible defaults for view tests."""
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
    ds = UnifiedDataset(**defaults)
    ds.distributions = [
        UnifiedDistribution(
            app=defaults['app'],
            name='test-dist',
            dataset_name=defaults['name'],
            title='Test Distribution',
        ),
    ]
    return ds


def _mock_schema():
    return {
        'dct:title': {
            'label': 'Title',
            'local_name': 'title',
            'min': 1,
            'max': 1,
        },
        'dct:description': {
            'label': 'Description',
            'local_name': 'description',
            'min': 1,
            'max': 1,
        },
        'dct:accessRights': {
            'label': 'Access Rights',
            'local_name': 'accessRights',
            'min': 1,
            'max': 1,
        },
    }


_SERVICE_PATH = 'warehouse.views.UnifiedCatalogService'


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
        response = self.client.get(reverse('warehouse:catalogue'))
        self.assertNotEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_returns_200_with_datasets(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [_make_test_dataset()]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('warehouse:catalogue'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Dataset')

    @patch(_SERVICE_PATH)
    def test_empty_catalogue(self, mock_cls):
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = []
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('warehouse:catalogue'))
        self.assertEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_text_search_filters(self, mock_cls):
        ds1 = _make_test_dataset(name='ds1', title='Alpha Dataset')
        ds2 = _make_test_dataset(name='ds2', title='Beta Dataset')
        mock_svc = mock_cls.return_value
        mock_svc.get_datasets_with_distributions.return_value = [ds1, ds2]
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(reverse('warehouse:catalogue'), {'q': 'Alpha'})
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

    @patch(_SERVICE_PATH)
    def test_returns_200_for_existing_dataset(self, mock_cls):
        ds = _make_test_dataset()
        mock_svc = mock_cls.return_value
        mock_svc.get_single_dataset.return_value = (ds, ds.distributions)
        mock_svc.get_schema_json.return_value = _mock_schema()

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'warehouse:dataset_detail', kwargs={'app': 'fair_genomes', 'name': 'test-dataset'}
            )
        )
        self.assertEqual(response.status_code, 200)

    @patch(_SERVICE_PATH)
    def test_missing_dataset_raises_404(self, mock_cls):
        """A non-existent dataset triggers Http404 in the view."""
        from django.http import Http404

        mock_svc = mock_cls.return_value
        mock_svc.get_single_dataset.return_value = (None, [])

        self.client.force_login(self.user)
        with self.assertRaises(Http404):
            # Call the view directly to verify the Http404 is raised,
            # bypassing the 404.html template (which has a known {% extends %} ordering issue).
            from django.test import RequestFactory

            from warehouse.views import DatasetDetailView

            factory = RequestFactory()
            request = factory.get('/dataset/fair_genomes/nonexistent/')
            request.user = self.user
            request.session = self.client.session
            with patch(_SERVICE_PATH) as inner_mock:
                inner_mock.return_value = mock_svc
                DatasetDetailView.as_view()(request, app='fair_genomes', name='nonexistent')
