"""
Tests for the warehouse application.

Covers models, views, template tags, and admin configuration.
"""

from django.test import TestCase

from .models import DataclassList, DataclassTableSchemes, DatasetList, DatasourceList, DbTableList


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
