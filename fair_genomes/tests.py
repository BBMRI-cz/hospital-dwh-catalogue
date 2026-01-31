"""
Fair Genomes App Tests

Test cases for Fair Genomes models, views, and services.
"""
from datetime import datetime
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from .models import Personal
from .views import PersonalListView, PersonalDetailView
from .services.fair_genomes_service import FairGenomesService, FairGenomesAPIException


class PersonalModelTest(TestCase):
    """Test cases for Personal model."""
    
    databases = {'default', 'fair_genomes_db'}
    
    def test_personal_str_representation(self):
        """Test string representation of Personal."""
        personal = Personal(
            personal_identifier='TEST-001',
            year_of_birth=1990
        )
        self.assertEqual(str(personal), 'TEST-001')
    
    def test_personal_repr(self):
        """Test repr of Personal."""
        personal = Personal(
            personal_identifier='TEST-001',
            year_of_birth=1990
        )
        self.assertIn('TEST-001', repr(personal))
        self.assertIn('1990', repr(personal))


class PersonalListViewTest(TestCase):
    """Test cases for PersonalListView."""
    
    databases = {'default', 'fair_genomes_db'}
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
    
    @patch('fair_genomes.views.Personal.objects')
    def test_list_view_returns_200(self, mock_objects):
        """Test that list view returns 200 status."""
        mock_objects.all.return_value = []
        mock_objects.count.return_value = 0
        mock_objects.exclude.return_value.values_list.return_value.distinct.return_value.order_by.return_value = []
        
        request = self.factory.get(reverse('fair_genomes:personal_list'))
        response = PersonalListView.as_view()(request)
        
        self.assertEqual(response.status_code, 200)


class FairGenomesServiceTest(TestCase):
    """Test cases for FairGenomesService."""
    
    def test_parse_datetime_valid(self):
        """Test parsing valid ISO datetime."""
        dt_string = '2024-01-15T10:30:00Z'
        result = FairGenomesService._parse_datetime(dt_string)
        
        self.assertIsNotNone(result)
        self.assertTrue(timezone.is_aware(result))
    
    def test_parse_datetime_none(self):
        """Test parsing None datetime."""
        result = FairGenomesService._parse_datetime(None)
        self.assertIsNone(result)
    
    def test_parse_datetime_invalid(self):
        """Test parsing invalid datetime."""
        result = FairGenomesService._parse_datetime('invalid-date')
        self.assertIsNone(result)
    
    @patch('fair_genomes.services.fair_genomes_service.requests.Session')
    def test_api_timeout_raises_exception(self, mock_session_class):
        """Test that timeout raises FairGenomesAPIException."""
        import requests
        
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.Timeout()
        
        with patch.object(FairGenomesService, '__init__', lambda x, **kwargs: None):
            service = FairGenomesService()
            service.api_url = 'http://test.example.com'
            service.api_token = 'test-token'
            service.timeout = 30
            service._session = mock_session
            
            with self.assertRaises(FairGenomesAPIException):
                service._execute_query('query { test }')
