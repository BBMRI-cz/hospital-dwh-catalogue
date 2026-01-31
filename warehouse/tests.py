"""
Warehouse App Tests

Test cases for warehouse models and views.
"""
from django.test import TestCase, RequestFactory
from django.urls import reverse
from unittest.mock import patch, MagicMock

from .views import CatalogueView


class CatalogueViewTest(TestCase):
    """Test cases for CatalogueView."""
    
    databases = {'default', 'metadata_db'}
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
    
    @patch('warehouse.views.DatasetList.objects')
    def test_catalogue_view_returns_200(self, mock_objects):
        """Test that catalogue view returns 200 status."""
        mock_objects.select_related.return_value.prefetch_related.return_value = []
        mock_objects.exclude.return_value.values_list.return_value = []
        mock_objects.values_list.return_value.distinct.return_value = []
        
        request = self.factory.get(reverse('warehouse:catalogue'))
        response = CatalogueView.as_view()(request)
        
        self.assertEqual(response.status_code, 200)
    
    @patch('warehouse.views.DatasetList.objects')
    def test_catalogue_view_search_filter(self, mock_objects):
        """Test that search query filters results."""
        mock_qs = MagicMock()
        mock_objects.select_related.return_value.prefetch_related.return_value = mock_qs
        mock_qs.filter.return_value.distinct.return_value = mock_qs
        mock_objects.exclude.return_value.values_list.return_value = []
        mock_objects.values_list.return_value.distinct.return_value = []
        
        request = self.factory.get(reverse('warehouse:catalogue'), {'query': 'test'})
        CatalogueView.as_view()(request)
        
        # Verify filter was called
        mock_qs.filter.assert_called_once()


class SubjectTagsParsingTest(TestCase):
    """Test cases for subject tags parsing logic."""
    
    def test_parse_comma_separated_tags(self):
        """Test parsing of comma-separated subject tags."""
        subject = "tag1, tag2, tag3"
        tags = [tag.strip() for tag in subject.split(',') if tag.strip()]
        
        self.assertEqual(tags, ['tag1', 'tag2', 'tag3'])
    
    def test_parse_empty_tags_filtered(self):
        """Test that empty tags are filtered out."""
        subject = "tag1, , tag3, "
        tags = [tag.strip() for tag in subject.split(',') if tag.strip()]
        
        self.assertEqual(tags, ['tag1', 'tag3'])
