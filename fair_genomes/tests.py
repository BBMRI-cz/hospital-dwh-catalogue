"""
Tests for the fair_genomes application.

Covers models, views, and the Fair Genomes API service.
"""

from unittest.mock import MagicMock, patch

import requests

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from .models import Personal
from .services.fair_genomes_service import FairGenomesAPIException, FairGenomesService
from .views import PersonalDetailView, PersonalListView


class PersonalModelTest(TestCase):
    """Tests for the Personal model."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_str_representation(self):
        """__str__ returns personal_identifier."""
        obj = Personal(personal_identifier='TEST-001')
        self.assertEqual(str(obj), 'TEST-001')

    def test_repr(self):
        """__repr__ returns expected format."""
        obj = Personal(personal_identifier='TEST-001', year_of_birth=1990)
        self.assertEqual(repr(obj), '<Personal: TEST-001 (born 1990)>')

    def test_meta_ordering(self):
        """Default ordering is by -inserted_on."""
        self.assertEqual(Personal._meta.ordering, ['-inserted_on'])

    def test_meta_db_table(self):
        """Model uses correct table name."""
        self.assertEqual(Personal._meta.db_table, 'fair_genomes_personal')

    def test_create_and_retrieve(self):
        """Personal record can be created and retrieved."""
        Personal.objects.using('fair_genomes_db').create(
            personal_identifier='TEST-002',
            year_of_birth=1985,
        )
        obj = Personal.objects.using('fair_genomes_db').get(personal_identifier='TEST-002')
        self.assertEqual(obj.year_of_birth, 1985)

    def test_nullable_fields(self):
        """Optional fields default to None."""
        obj = Personal(personal_identifier='TEST-003')
        self.assertIsNone(obj.year_of_birth)
        self.assertIsNone(obj.inserted_by)
        self.assertIsNone(obj.inserted_on)


class FairGenomesServiceTest(TestCase):
    """Tests for FairGenomesService."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def test_parse_datetime_valid_utc(self):
        """Parses ISO datetime with Z suffix."""
        result = FairGenomesService._parse_datetime('2024-01-15T10:30:00Z')
        self.assertIsNotNone(result)
        assert result is not None  # Type guard for mypy
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_datetime_valid_offset(self):
        """Parses ISO datetime with timezone offset."""
        result = FairGenomesService._parse_datetime('2024-01-15T10:30:00+02:00')
        self.assertIsNotNone(result)
        assert result is not None  # Type guard for mypy
        self.assertEqual(result.year, 2024)

    def test_parse_datetime_none_input(self):
        """Returns None for None input."""
        result = FairGenomesService._parse_datetime(None)
        self.assertIsNone(result)

    def test_parse_datetime_empty_string(self):
        """Returns None for empty string."""
        result = FairGenomesService._parse_datetime('')
        self.assertIsNone(result)

    def test_parse_datetime_invalid_format(self):
        """Returns None for invalid datetime string."""
        result = FairGenomesService._parse_datetime('not-a-datetime')
        self.assertIsNone(result)

    def test_service_init_defaults(self):
        """Service uses Django settings by default."""
        with self.settings(
            FAIR_GENOMES_API_URL='http://test.example.com/graphql',
            FAIR_GENOMES_API_TOKEN='test-token',
        ):
            service = FairGenomesService()
            self.assertEqual(service.api_url, 'http://test.example.com/graphql')
            self.assertEqual(service.api_token, 'test-token')
            self.assertEqual(service.timeout, 30)

    def test_service_init_custom_params(self):
        """Service accepts custom parameters."""
        service = FairGenomesService(
            api_url='http://custom.example.com/graphql',
            api_token='custom-token',
            timeout=60,
        )
        self.assertEqual(service.api_url, 'http://custom.example.com/graphql')
        self.assertEqual(service.api_token, 'custom-token')
        self.assertEqual(service.timeout, 60)

    @patch('fair_genomes.services.fair_genomes_service.requests.Session')
    def test_execute_query_timeout(self, mock_session_cls):
        """Timeout raises FairGenomesAPIException."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.Timeout()

        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        service._session = mock_session

        with self.assertRaises(FairGenomesAPIException) as ctx:
            service._execute_query('query { test }')
        self.assertIn('timed out', str(ctx.exception))

    @patch('fair_genomes.services.fair_genomes_service.requests.Session')
    def test_execute_query_connection_error(self, mock_session_cls):
        """Connection error raises FairGenomesAPIException."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.ConnectionError('refused')

        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        service._session = mock_session

        with self.assertRaises(FairGenomesAPIException) as ctx:
            service._execute_query('query { test }')
        self.assertIn('Failed to connect', str(ctx.exception))

    @patch('fair_genomes.services.fair_genomes_service.requests.Session')
    def test_execute_query_graphql_errors(self, mock_session_cls):
        """GraphQL errors in response raise FairGenomesAPIException."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {'errors': [{'message': 'Field not found'}]}
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        service._session = mock_session

        with self.assertRaises(FairGenomesAPIException) as ctx:
            service._execute_query('query { badField }')
        self.assertIn('Field not found', str(ctx.exception))

    @patch('fair_genomes.services.fair_genomes_service.requests.Session')
    def test_execute_query_success(self, mock_session_cls):
        """Successful query returns data."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'Personal': [{'id': '1'}]}}
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        service._session = mock_session

        result = service._execute_query('query { Personal { id } }')
        self.assertEqual(result, {'Personal': [{'id': '1'}]})

    def test_context_manager(self):
        """Service works as context manager."""
        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        with service as svc:
            self.assertIsInstance(svc, FairGenomesService)
        self.assertIsNone(service._session)

    def test_close_without_session(self):
        """Closing without a session does not raise."""
        service = FairGenomesService(api_url='http://test.com/graphql', api_token='token')
        service.close()  # Should not raise


class PersonalListViewTest(TestCase):
    """Tests for the PersonalListView."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )

    @patch('fair_genomes.views.Personal.objects')
    def test_view_returns_200(self, mock_objects):
        """Authenticated user gets 200 response."""
        mock_qs = MagicMock()
        mock_objects.all.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_objects.count.return_value = 0
        mock_objects.exclude.return_value.values_list.return_value.distinct.return_value.order_by.return_value = []

        request = self.factory.get('/fair-genomes/')
        request.user = self.user
        response = PersonalListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_view_redirects_unauthenticated(self):
        """Unauthenticated users are redirected."""
        request = self.factory.get('/fair-genomes/')
        request.user = AnonymousUser()
        response = PersonalListView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    @patch('fair_genomes.views.Personal.objects')
    def test_view_search_filters_queryset(self, mock_objects):
        """Search query filters the queryset."""
        mock_qs = MagicMock()
        mock_objects.all.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_objects.count.return_value = 0
        mock_objects.exclude.return_value.values_list.return_value.distinct.return_value.order_by.return_value = []

        request = self.factory.get('/fair-genomes/', {'query': 'TEST'})
        request.user = self.user
        PersonalListView.as_view()(request)
        mock_qs.filter.assert_called()

    @patch('fair_genomes.views.Personal.objects')
    def test_view_yob_filter(self, mock_objects):
        """Year of birth filter is applied."""
        mock_qs = MagicMock()
        mock_objects.all.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_objects.count.return_value = 0
        mock_objects.exclude.return_value.values_list.return_value.distinct.return_value.order_by.return_value = []

        request = self.factory.get('/fair-genomes/', {'yob': '1990'})
        request.user = self.user
        PersonalListView.as_view()(request)
        mock_qs.filter.assert_called()

    @patch('fair_genomes.views.Personal.objects')
    def test_view_invalid_yob_ignored(self, mock_objects):
        """Invalid year of birth value is silently ignored."""
        mock_qs = MagicMock()
        mock_objects.all.return_value = mock_qs
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_objects.count.return_value = 0
        mock_objects.exclude.return_value.values_list.return_value.distinct.return_value.order_by.return_value = []

        request = self.factory.get('/fair-genomes/', {'yob': 'invalid'})
        request.user = self.user
        # Should not raise
        response = PersonalListView.as_view()(request)
        self.assertEqual(response.status_code, 200)


class PersonalDetailViewTest(TestCase):
    """Tests for the PersonalDetailView."""

    databases = {'default', 'auth_db', 'fair_genomes_db'}

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
        )

    def test_view_redirects_unauthenticated(self):
        """Unauthenticated users are redirected."""
        request = self.factory.get('/fair-genomes/TEST-001/')
        request.user = AnonymousUser()
        response = PersonalDetailView.as_view()(request, pk='TEST-001')
        self.assertEqual(response.status_code, 302)
