"""
Tests for the warehouse application.

Covers models, views, template tags, and admin configuration.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from .models import DataclassList, DataclassTableSchemes, DatasetList, DatasourceList, DbTableList
from .views import CatalogueView


class DatasourceListModelTest(TestCase):
    """Tests for the DatasourceList model."""

    databases = {'default', 'auth_db'}

    def test_str_with_name(self):
        """Model __str__ returns data_source_name when available."""
        obj = DatasourceList(data_source='ds1', data_source_name='Data Source 1')
        self.assertEqual(str(obj), 'Data Source 1')

    def test_str_without_name(self):
        """Model __str__ falls back to data_source when name is empty."""
        obj = DatasourceList(data_source='ds1', data_source_name='')
        self.assertEqual(str(obj), 'ds1')

    def test_str_with_none_name(self):
        """Model __str__ falls back to data_source when name is None."""
        obj = DatasourceList(data_source='ds1', data_source_name=None)
        self.assertEqual(str(obj), 'ds1')

    def test_display_name_with_name(self):
        """display_name returns data_source_name when available."""
        obj = DatasourceList(data_source='ds1', data_source_name='Data Source 1')
        self.assertEqual(obj.display_name, 'Data Source 1')

    def test_display_name_without_name(self):
        """display_name falls back to data_source."""
        obj = DatasourceList(data_source='ds1', data_source_name='')
        self.assertEqual(obj.display_name, 'ds1')

    def test_meta_managed_false(self):
        """Model is unmanaged (read-only)."""
        self.assertFalse(DatasourceList._meta.managed)


class DatasetListModelTest(TestCase):
    """Tests for the DatasetList model."""

    databases = {'default', 'auth_db'}

    def test_str_with_name(self):
        """Model __str__ returns data_set_name when available."""
        obj = DatasetList(data_set='ds1', data_set_name='Dataset 1')
        self.assertEqual(str(obj), 'Dataset 1')

    def test_str_without_name(self):
        """Model __str__ falls back to data_set."""
        obj = DatasetList(data_set='ds1', data_set_name='')
        self.assertEqual(str(obj), 'ds1')

    def test_display_name(self):
        """display_name returns data_set_name when available."""
        obj = DatasetList(data_set='ds1', data_set_name='Dataset 1')
        self.assertEqual(obj.display_name, 'Dataset 1')

    def test_display_name_fallback(self):
        """display_name falls back to data_set."""
        obj = DatasetList(data_set='ds1', data_set_name='')
        self.assertEqual(obj.display_name, 'ds1')

    def test_is_complete_true(self):
        """is_complete returns True when complete is 'ano'."""
        obj = DatasetList(data_set='ds1', complete='ano')
        self.assertTrue(obj.is_complete)

    def test_is_complete_case_insensitive(self):
        """is_complete is case insensitive."""
        obj = DatasetList(data_set='ds1', complete='Ano')
        self.assertTrue(obj.is_complete)

    def test_is_complete_false(self):
        """is_complete returns False for non-'ano' values."""
        obj = DatasetList(data_set='ds1', complete='ne')
        self.assertFalse(obj.is_complete)

    def test_is_complete_none(self):
        """is_complete returns False when complete is None."""
        obj = DatasetList(data_set='ds1', complete=None)
        self.assertFalse(obj.is_complete)

    def test_subject_tags_list(self):
        """subject_tags_list parses comma-separated tags."""
        obj = DatasetList(data_set='ds1', subject='tag1, tag2, tag3')
        self.assertEqual(obj.subject_tags_list, ['tag1', 'tag2', 'tag3'])

    def test_subject_tags_list_empty(self):
        """subject_tags_list returns empty list when subject is empty."""
        obj = DatasetList(data_set='ds1', subject='')
        self.assertEqual(obj.subject_tags_list, [])

    def test_subject_tags_list_none(self):
        """subject_tags_list returns empty list when subject is None."""
        obj = DatasetList(data_set='ds1', subject=None)
        self.assertEqual(obj.subject_tags_list, [])

    def test_subject_tags_list_strips_whitespace(self):
        """subject_tags_list strips whitespace from tags."""
        obj = DatasetList(data_set='ds1', subject=' tag1 ,  tag2 ')
        self.assertEqual(obj.subject_tags_list, ['tag1', 'tag2'])

    def test_meta_managed_false(self):
        """Model is unmanaged."""
        self.assertFalse(DatasetList._meta.managed)

    def test_meta_ordering(self):
        """Default ordering is by data_set_name."""
        self.assertEqual(DatasetList._meta.ordering, ['data_set_name'])


class DataclassListModelTest(TestCase):
    """Tests for the DataclassList model."""

    databases = {'default', 'auth_db'}

    def test_str_with_name(self):
        """Model __str__ returns data_class_name when available."""
        obj = DataclassList(data_class='dc1', data_class_name='Data Class 1')
        self.assertEqual(str(obj), 'Data Class 1')

    def test_str_without_name(self):
        """Model __str__ falls back to data_class."""
        obj = DataclassList(data_class='dc1', data_class_name='')
        self.assertEqual(str(obj), 'dc1')

    def test_display_name(self):
        """display_name property returns correct value."""
        obj = DataclassList(data_class='dc1', data_class_name='Data Class 1')
        self.assertEqual(obj.display_name, 'Data Class 1')

    def test_is_complete_true(self):
        """is_complete returns True for 'ano'."""
        obj = DataclassList(data_class='dc1', complete='ano')
        self.assertTrue(obj.is_complete)

    def test_is_complete_false(self):
        """is_complete returns False for non-'ano' values."""
        obj = DataclassList(data_class='dc1', complete='ne')
        self.assertFalse(obj.is_complete)

    def test_has_repository_true(self):
        """has_repository returns True when repository has value."""
        obj = DataclassList(data_class='dc1', repository='repo1')
        self.assertTrue(obj.has_repository)

    def test_has_repository_false_empty(self):
        """has_repository returns False for empty string."""
        obj = DataclassList(data_class='dc1', repository='')
        self.assertFalse(obj.has_repository)

    def test_has_repository_false_whitespace(self):
        """has_repository returns False for whitespace-only string."""
        obj = DataclassList(data_class='dc1', repository='  ')
        self.assertFalse(obj.has_repository)

    def test_has_repository_false_none(self):
        """has_repository returns False for None."""
        obj = DataclassList(data_class='dc1', repository=None)
        self.assertFalse(obj.has_repository)

    def test_meta_managed_false(self):
        """Model is unmanaged."""
        self.assertFalse(DataclassList._meta.managed)


class DataclassTableSchemesModelTest(TestCase):
    """Tests for the DataclassTableSchemes model."""

    databases = {'default', 'auth_db'}

    def test_str(self):
        """Model __str__ returns expected format."""
        obj = DataclassTableSchemes(data_class='dc1', col_name='Column 1')
        self.assertEqual(str(obj), 'dc1 - Column 1')

    def test_meta_managed_false(self):
        """Model is unmanaged."""
        self.assertFalse(DataclassTableSchemes._meta.managed)


class DbTableListModelTest(TestCase):
    """Tests for the DbTableList model."""

    databases = {'default', 'auth_db'}

    def test_str_with_name(self):
        """Model __str__ returns db_table_name when available."""
        obj = DbTableList(db_table='tbl1', db_table_name='Table 1')
        self.assertEqual(str(obj), 'Table 1')

    def test_str_without_name(self):
        """Model __str__ falls back to db_table."""
        obj = DbTableList(db_table='tbl1', db_table_name='')
        self.assertEqual(str(obj), 'tbl1')

    def test_display_name(self):
        """display_name returns db_table_name when available."""
        obj = DbTableList(db_table='tbl1', db_table_name='Table 1')
        self.assertEqual(obj.display_name, 'Table 1')

    def test_display_name_fallback(self):
        """display_name falls back to db_table."""
        obj = DbTableList(db_table='tbl1', db_table_name='')
        self.assertEqual(obj.display_name, 'tbl1')

    def test_meta_managed_false(self):
        """Model is unmanaged."""
        self.assertFalse(DbTableList._meta.managed)


class CatalogueViewTest(TestCase):
    """Tests for the CatalogueView."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )

    def _setup_catalogue_mocks(self, mock_objects):
        """Configure mocks for CatalogueView context data lookups."""
        mock_qs = MagicMock()
        mock_objects.select_related.return_value.prefetch_related.return_value = mock_qs
        mock_qs.filter.return_value.distinct.return_value = mock_qs
        mock_qs.count.return_value = 0

        # Mock subject tags: exclude().values_list()
        mock_objects.exclude.return_value.values_list.return_value = []

        # Mock data sources: values_list().distinct()
        mock_vl_qs = MagicMock()
        mock_vl_qs.distinct.return_value = []
        mock_objects.values_list.return_value = mock_vl_qs

        # Mock rights holders: exclude().values_list().distinct()
        mock_exclude_qs = MagicMock()
        mock_exclude_vl = MagicMock()
        mock_exclude_vl.distinct.return_value = []
        mock_exclude_qs.values_list.return_value = mock_exclude_vl
        mock_objects.exclude.return_value = mock_exclude_qs

        return mock_qs

    @patch('warehouse.views.DatasetList.objects')
    def test_view_returns_200(self, mock_objects):
        """Authenticated user gets 200 response."""
        self._setup_catalogue_mocks(mock_objects)

        request = self.factory.get('/warehouse/')
        request.user = self.user
        response = CatalogueView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    @patch('warehouse.views.DatasetList.objects')
    def test_view_applies_search_filter(self, mock_objects):
        """Search query triggers queryset filtering."""
        mock_qs = self._setup_catalogue_mocks(mock_objects)

        request = self.factory.get('/warehouse/', {'query': 'diabetes'})
        request.user = self.user
        CatalogueView.as_view()(request)
        mock_qs.filter.assert_called_once()

    @patch('warehouse.views.DatasetList.objects')
    def test_view_no_filter_without_query(self, mock_objects):
        """No filter is applied when query is empty."""
        mock_qs = self._setup_catalogue_mocks(mock_objects)

        request = self.factory.get('/warehouse/')
        request.user = self.user
        CatalogueView.as_view()(request)
        mock_qs.filter.assert_not_called()

    def test_view_redirects_unauthenticated(self):
        """Unauthenticated users are redirected to login."""
        request = self.factory.get('/warehouse/')
        request.user = AnonymousUser()
        response = CatalogueView.as_view()(request)
        self.assertEqual(response.status_code, 302)
