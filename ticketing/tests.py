"""
Tests for the ticketing application.

Covers models, forms, views, services, and cart functionality.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from shared.dtos import UnifiedDataset
from ticketing.cart import CART_MAX_ITEMS, CartService

from .models import TicketRequest, TicketRequestItem
from .services.alvao_service import AlvaoService, AlvaoServiceException
from .services.base import AlvaoPriority, TicketData, TicketResponse
from .services.factory import get_ticket_service
from .services.mock_service import MockAlvaoService
from .services.ticketing_service import TicketingService


class StaticTicketBackend:
    """Deterministic ticket backend for view tests."""

    def create_ticket(self, ticket_data):
        return TicketResponse(ticket_id='T-100', ticket_number='T-100', status='New')


class CapturingTicketBackend(StaticTicketBackend):
    """Ticket backend that stores the submitted payload for assertions."""

    def __init__(self):
        self.ticket_data = None

    def create_ticket(self, ticket_data):
        self.ticket_data = ticket_data
        return super().create_ticket(ticket_data)


class FailingTicketBackend:
    """Ticket backend that simulates an external submission failure."""

    def create_ticket(self, ticket_data):
        raise RuntimeError('ALVAO is unavailable')


class FakeAlvaoResponse:
    def __init__(self, *, status_code, json_data=None, text=''):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError('No JSON body')
        return self._json_data


class FakeAlvaoSession:
    def __init__(self, response):
        self.responses = list(response) if isinstance(response, (list, tuple)) else [response]
        self.requests = []

    def request(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


class TicketRequestModelTest(TestCase):
    """Tests for the TicketRequest model."""

    databases = {'default', 'auth_db'}

    def test_str_with_alvao_id(self):
        """__str__ includes Alvao ticket ID when available."""
        obj = TicketRequest(
            subject='Test Subject',
            alvao_ticket_id='T-12345',
            requester_email='test@example.com',
        )
        result = str(obj)
        self.assertIn('T-12345', result)
        self.assertIn('Test Subject', result)

    def test_str_without_alvao_id(self):
        """__str__ shows 'Draft' when no Alvao ID."""
        obj = TicketRequest(
            subject='Test Subject',
            requester_email='test@example.com',
        )
        result = str(obj)
        self.assertIn('Draft', result)
        self.assertIn('Test Subject', result)

    def test_str_truncates_long_subject(self):
        """__str__ truncates subject to 50 characters."""
        long_subject = 'A' * 100
        obj = TicketRequest(subject=long_subject, requester_email='test@example.com')
        result = str(obj)
        self.assertLessEqual(len(result), 60)

    def test_is_submitted_true(self):
        """is_submitted returns True for submitted status."""
        obj = TicketRequest(status=TicketRequest.Status.SUBMITTED, requester_email='t@e.com')
        self.assertTrue(obj.is_submitted)

    def test_is_submitted_confirmed(self):
        """is_submitted returns True for confirmed status."""
        obj = TicketRequest(status=TicketRequest.Status.CONFIRMED, requester_email='t@e.com')
        self.assertTrue(obj.is_submitted)

    def test_is_submitted_false_draft(self):
        """is_submitted returns False for draft status."""
        obj = TicketRequest(status=TicketRequest.Status.DRAFT, requester_email='t@e.com')
        self.assertFalse(obj.is_submitted)

    def test_is_submitted_false_failed(self):
        """is_submitted returns False for failed status."""
        obj = TicketRequest(status=TicketRequest.Status.FAILED, requester_email='t@e.com')
        self.assertFalse(obj.is_submitted)

    def test_create_ticket_request(self):
        """TicketRequest can be created in database."""
        ticket = TicketRequest.objects.create(
            requester_email='test@example.com',
            requester_name='Test User',
            subject='Test Ticket',
            description='Test description',
        )
        self.assertEqual(ticket.status, TicketRequest.Status.DRAFT)
        self.assertIsNotNone(ticket.created_at)

    def test_item_count(self):
        """item_count returns correct number of items."""
        ticket = TicketRequest.objects.create(
            requester_email='test@example.com',
            subject='Test',
        )
        TicketRequestItem.objects.create(
            ticket_request=ticket,
            item_type=TicketRequestItem.ItemType.DATASET,
            item_id='ds1',
            item_name='Dataset 1',
        )
        TicketRequestItem.objects.create(
            ticket_request=ticket,
            item_type=TicketRequestItem.ItemType.TABLE,
            item_id='tbl1',
            item_name='Table 1',
        )
        self.assertEqual(ticket.item_count, 2)

    def test_status_choices(self):
        """All expected status choices exist."""
        choices = [c[0] for c in TicketRequest.Status.choices]
        self.assertIn('draft', choices)
        self.assertIn('submitted', choices)
        self.assertIn('confirmed', choices)
        self.assertIn('failed', choices)

    def test_meta_ordering(self):
        """Default ordering is -created_at."""
        self.assertEqual(TicketRequest._meta.ordering, ['-created_at'])


class TicketRequestItemModelTest(TestCase):
    """Tests for the TicketRequestItem model."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.ticket = TicketRequest.objects.create(
            requester_email='test@example.com',
            subject='Test',
        )

    def test_str_representation(self):
        """__str__ shows item type label and name."""
        item = TicketRequestItem(
            ticket_request=self.ticket,
            item_type=TicketRequestItem.ItemType.DATASET,
            item_id='ds1',
            item_name='Dataset 1',
        )
        result = str(item)
        self.assertIn('Dataset 1', result)

    def test_item_type_choices(self):
        """All expected item type choices exist."""
        choices = [c[0] for c in TicketRequestItem.ItemType.choices]
        self.assertIn('dataset', choices)
        self.assertIn('dataclass', choices)
        self.assertIn('table', choices)

    def test_cascade_delete(self):
        """Items are deleted when ticket request is deleted."""
        TicketRequestItem.objects.create(
            ticket_request=self.ticket,
            item_type=TicketRequestItem.ItemType.DATASET,
            item_id='ds1',
            item_name='Dataset 1',
        )
        ticket_pk = self.ticket.pk
        self.ticket.delete()
        self.assertEqual(TicketRequestItem.objects.filter(ticket_request_id=ticket_pk).count(), 0)

    def test_unique_together(self):
        """Same item type+id cannot be added twice to one ticket."""
        TicketRequestItem.objects.create(
            ticket_request=self.ticket,
            item_type=TicketRequestItem.ItemType.DATASET,
            item_id='ds1',
            item_name='Dataset 1',
        )

        with self.assertRaises(IntegrityError):
            TicketRequestItem.objects.create(
                ticket_request=self.ticket,
                item_type=TicketRequestItem.ItemType.DATASET,
                item_id='ds1',
                item_name='Dataset 1 duplicate',
            )


class TicketDataTest(TestCase):
    """Tests for the TicketData dataclass."""

    def test_to_dict(self):
        """to_dict converts to Alvao v1.3 API payload format."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
            requester_name='Test User',
        )
        result = data.to_dict()
        self.assertEqual(result['name'], 'Test')
        self.assertEqual(result['descriptionHtml'], 'Desc')
        self.assertEqual(result['requester']['email'], 'test@example.com')
        self.assertEqual(result['requester']['name'], 'Test User')
        self.assertNotIn('priority', result)

    def test_to_dict_includes_priority_only_when_explicit(self):
        """Priority is optional because Alvao instances can have custom values."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
            priority=AlvaoPriority.MEDIUM,
        )

        result = data.to_dict()

        self.assertEqual(result['priority'], 'Medium')

    def test_to_dict_minimal(self):
        """to_dict with only required fields."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
        )
        result = data.to_dict()
        self.assertIn('name', result)
        self.assertIn('requester', result)
        self.assertNotIn('priority', result)
        self.assertNotIn('serviceId', result)

    def test_to_dict_omits_requester_without_email(self):
        """Requester is omitted when no requester email is available."""
        data = TicketData(subject='Test', description='Desc')

        result = data.to_dict()

        self.assertEqual(result['name'], 'Test')
        self.assertNotIn('requester', result)

    def test_to_dict_with_service_id(self):
        """to_dict includes service_id when set."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
            service_id=42,
        )
        result = data.to_dict()
        self.assertEqual(result['serviceId'], 42)


class TicketResponseTest(TestCase):
    """Tests for the TicketResponse dataclass."""

    def test_from_dict(self):
        """from_dict creates instance from Alvao v1.3 API response."""
        response = TicketResponse.from_dict(
            {
                'id': 123,
                'messageTag': 'T137SD',
                'stateName': 'New',
                '_links': {'self': {'href': 'https://alvao.example.com/api/tickets/123'}},
            }
        )
        self.assertEqual(response.ticket_id, '123')
        self.assertEqual(response.ticket_number, 'T137SD')
        self.assertEqual(response.status, 'New')
        self.assertEqual(response.url, 'https://alvao.example.com/api/tickets/123')

    def test_from_dict_minimal(self):
        """from_dict handles response with only id."""
        response = TicketResponse.from_dict({'id': 456})
        self.assertEqual(response.ticket_id, '456')
        self.assertIsNone(response.ticket_number)
        self.assertIsNone(response.status)
        self.assertIsNone(response.url)


class MockAlvaoServiceTest(TestCase):
    """Tests for the MockAlvaoService."""

    databases = {'default', 'auth_db'}

    def test_create_ticket(self):
        """Mock service creates a ticket and returns response."""
        service = MockAlvaoService(use_database=False)
        ticket_data = TicketData(
            subject='Test Ticket',
            description='Test',
            requester_email='test@example.com',
        )
        response = service.create_ticket(ticket_data)
        self.assertIsInstance(response, TicketResponse)
        self.assertTrue(response.ticket_id.startswith('MOCK-'))
        self.assertIsNotNone(response.ticket_number)

    def test_create_ticket_stores_in_memory(self):
        """Mock service stores ticket in memory."""
        service = MockAlvaoService(use_database=False)
        ticket_data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
        )
        response = service.create_ticket(ticket_data)
        self.assertIsNotNone(response.ticket_id)
        self.assertEqual(response.status, 'New')


class GetTicketServiceTest(TestCase):
    """Tests for the service factory."""

    def test_returns_mock_when_configured(self):
        """Factory returns MockAlvaoService when MOCK_ALVAO is True."""
        with self.settings(MOCK_ALVAO=True):
            service = get_ticket_service()
            self.assertIsInstance(service, MockAlvaoService)

    def test_returns_alvao_when_not_mock(self):
        """Factory returns AlvaoService when MOCK_ALVAO is False."""
        with self.settings(MOCK_ALVAO=False):
            service = get_ticket_service()
            self.assertIsInstance(service, AlvaoService)


class AlvaoServiceTest(TestCase):
    def test_create_ticket_injects_default_service(self):
        user_response = FakeAlvaoResponse(
            status_code=200,
            json_data={'value': [{'id': 321, 'email': 'test@example.com'}]},
        )
        ticket_response = FakeAlvaoResponse(
            status_code=201,
            json_data={'id': 123, 'messageTag': 'T123SD', 'stateName': 'New'},
        )
        session = FakeAlvaoSession([user_response, ticket_response])
        service = AlvaoService(
            api_url='https://alvao.example/AlvaoRestApi/v1',
            default_service_id=109,
        )
        service._session = session

        result = service.create_ticket(
            TicketData(
                subject='Test',
                description='Desc',
                requester_email='test@example.com',
                requester_name='Test User',
            )
        )

        self.assertEqual(result.ticket_id, '123')
        self.assertEqual(session.requests[0]['method'], 'GET')
        self.assertEqual(session.requests[0]['params']['$search'], 'test@example.com')
        self.assertEqual(session.requests[1]['method'], 'POST')
        self.assertEqual(session.requests[1]['json']['serviceId'], 109)
        self.assertEqual(session.requests[1]['json']['requester'], {'id': 321})

    def test_create_ticket_resolves_service_account_when_requester_is_missing(self):
        user_response = FakeAlvaoResponse(
            status_code=200,
            json_data={'value': [{'id': 555, 'userName': 'SR_Alvao_Servicedesk_DWH'}]},
        )
        ticket_response = FakeAlvaoResponse(
            status_code=201,
            json_data={'id': 123, 'messageTag': 'T123SD', 'stateName': 'New'},
        )
        session = FakeAlvaoSession([user_response, ticket_response])
        service = AlvaoService(
            api_url='https://alvao.example/AlvaoRestApi/v1',
            service_account_username='SR_Alvao_Servicedesk_DWH',
            default_service_id=109,
        )
        service._session = session

        service.create_ticket(TicketData(subject='Test', description='Desc'))

        self.assertEqual(session.requests[0]['params']['$search'], 'SR_Alvao_Servicedesk_DWH')
        self.assertEqual(session.requests[1]['json']['requester'], {'id': 555})

    def test_create_ticket_accepts_alvao_capitalized_user_fields(self):
        user_response = FakeAlvaoResponse(
            status_code=200,
            json_data={'value': [{'Id': 321, 'Email': 'test@example.com'}]},
        )
        ticket_response = FakeAlvaoResponse(
            status_code=201,
            json_data={'id': 123, 'messageTag': 'T123SD', 'stateName': 'New'},
        )
        session = FakeAlvaoSession([user_response, ticket_response])
        service = AlvaoService(api_url='https://alvao.example/AlvaoRestApi/v1')
        service._session = session

        service.create_ticket(
            TicketData(subject='Test', description='Desc', requester_email='test@example.com')
        )

        self.assertEqual(session.requests[1]['json']['requester'], {'id': 321})

    def test_create_ticket_falls_back_to_unprefixed_search_param(self):
        empty_search_response = FakeAlvaoResponse(status_code=400, json_data={'value': []})
        user_response = FakeAlvaoResponse(
            status_code=200,
            json_data={'value': [{'id': 321, 'email': 'test@example.com'}]},
        )
        ticket_response = FakeAlvaoResponse(
            status_code=201,
            json_data={'id': 123, 'messageTag': 'T123SD', 'stateName': 'New'},
        )
        session = FakeAlvaoSession([empty_search_response, user_response, ticket_response])
        service = AlvaoService(api_url='https://alvao.example/AlvaoRestApi/v1')
        service._session = session

        service.create_ticket(
            TicketData(subject='Test', description='Desc', requester_email='test@example.com')
        )

        self.assertEqual(session.requests[0]['params']['$search'], 'test@example.com')
        self.assertEqual(session.requests[1]['params']['search'], 'test@example.com')
        self.assertEqual(session.requests[2]['json']['requester'], {'id': 321})

    def test_create_ticket_fails_when_requester_cannot_be_resolved(self):
        service = AlvaoService(api_url='https://alvao.example/AlvaoRestApi/v1')
        service._session = FakeAlvaoSession(
            FakeAlvaoResponse(status_code=200, json_data={'value': []})
        )

        with self.assertRaises(AlvaoServiceException) as context:
            service.create_ticket(
                TicketData(
                    subject='Test', description='Desc', requester_email='missing@example.com'
                )
            )

        self.assertIn('Could not resolve Alvao requester ID', str(context.exception))

    def test_create_ticket_does_not_fallback_to_service_account_for_named_requester(self):
        service = AlvaoService(
            api_url='https://alvao.example/AlvaoRestApi/v1',
            service_account_username='SR_Alvao_Servicedesk_DWH',
        )
        service._session = FakeAlvaoSession(
            FakeAlvaoResponse(status_code=200, json_data={'value': []})
        )

        with self.assertRaises(AlvaoServiceException):
            service.create_ticket(
                TicketData(
                    subject='Test', description='Desc', requester_email='missing@example.com'
                )
            )

        requested_params = [request['params'] for request in service._session.requests]
        self.assertEqual(
            requested_params,
            [
                {'$search': 'missing@example.com', '$top': 20},
                {'search': 'missing@example.com', 'top': 20},
            ],
        )

    def test_400_error_logs_response_body_and_extracts_validation_message(self):
        service = AlvaoService(api_url='https://alvao.example/AlvaoRestApi/v1')
        service._session = FakeAlvaoSession(
            FakeAlvaoResponse(
                status_code=400,
                json_data={
                    'title': 'One or more validation errors occurred.',
                    'errors': {'priority': ['The value Medium is invalid.']},
                },
            )
        )

        with (
            self.assertLogs('ticketing.services.alvao_service', level='ERROR') as logs,
            self.assertRaises(AlvaoServiceException) as context,
        ):
            service._make_request('POST', '/tickets', data={'name': 'Test'})

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn('One or more validation errors occurred.', str(context.exception))
        self.assertIn('"priority": ["The value Medium is invalid."]', logs.output[0])

    def test_sla_error_logs_service_account_requester_mode(self):
        service = AlvaoService(
            api_url='https://alvao.example/AlvaoRestApi/v1',
            service_account_username='Host',
        )
        service._session = FakeAlvaoSession(
            FakeAlvaoResponse(
                status_code=400,
                json_data={
                    'error': {
                        'code': '400',
                        'message': (
                            'The requester Host has no SLA for the service '
                            'Machala Testovací služba.'
                        ),
                    },
                },
            )
        )

        with (
            self.assertLogs('ticketing.services.alvao_service', level='ERROR') as logs,
            self.assertRaises(AlvaoServiceException),
        ):
            service._make_request('POST', '/tickets', data={'name': 'Test', 'serviceId': 109})

        output = '\n'.join(logs.output)
        self.assertIn('requester_mode=service_account', output)
        self.assertIn('requester=<omitted>', output)
        self.assertIn('service_id=109', output)


class CartAddViewTest(TestCase):
    """Regression tests for cart add/toggle AJAX behavior."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='cart-user',
            email='cart@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)
        self.url = reverse('ticketing:cart_add')

    def _dataset(
        self,
        *,
        app: str = 'warehouse',
        name: str = 'dataset-1',
        title: str = 'Canonical Dataset 1',
    ) -> UnifiedDataset:
        return UnifiedDataset(app=app, name=name, title=title)

    def test_ajax_add_stores_item_and_returns_count(self):
        """AJAX add stores the canonical cart item and reports in_cart/count."""
        with mock.patch(
            'ticketing.views.resolve_cart_dataset',
            return_value=self._dataset(title='Canonical Dataset 1'),
        ):
            response = self.client.post(
                self.url,
                data={'app': 'warehouse', 'name': 'dataset-1', 'title': 'Client Title'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['in_cart'])
        self.assertEqual(payload['cart_count'], 1)

        cart = self.client.session.get('cart', [])
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart[0]['app'], 'warehouse')
        self.assertEqual(cart[0]['name'], 'dataset-1')
        self.assertEqual(cart[0]['title'], 'Canonical Dataset 1')

    def test_ajax_toggle_same_item_removes_from_cart(self):
        """Posting the same item twice toggles it out of the cart."""
        data = {'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'}

        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            first_response = self.client.post(
                self.url,
                data=data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            second_response = self.client.post(
                self.url,
                data=data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertTrue(first_response.json()['in_cart'])

        payload = second_response.json()
        self.assertTrue(payload['success'])
        self.assertFalse(payload['in_cart'])
        self.assertEqual(payload['cart_count'], 0)
        self.assertEqual(self.client.session.get('cart', []), [])

    def test_htmx_add_returns_partial_with_oob_badge(self):
        """HTMX add returns the updated button fragment plus an OOB cart badge swap."""
        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            response = self.client.post(
                self.url,
                data={'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'},
                HTTP_HX_REQUEST='true',
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cart-badge"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertContains(response, 'bg-red-600')

    def test_htmx_inline_add_preserves_inline_button_contract(self):
        """HTMX inline toggle keeps the inline button payload and cart badge fragment."""
        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            response = self.client.post(
                self.url,
                data={
                    'app': 'warehouse',
                    'name': 'dataset-1',
                    'title': 'Dataset 1',
                    'btn_style': 'inline',
                },
                HTTP_HX_REQUEST='true',
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"btn_style": "inline"')
        self.assertContains(response, 'id="cart-badge"')

    def test_ajax_missing_required_param_is_noop_with_json_shape(self):
        """Missing app/name keeps cart unchanged and still returns expected JSON keys."""
        response = self.client.post(
            self.url,
            data={'source': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload.keys()), {'success', 'in_cart', 'cart_count'})
        self.assertTrue(payload['success'])
        self.assertFalse(payload['in_cart'])
        self.assertEqual(payload['cart_count'], 0)
        self.assertEqual(self.client.session.get('cart', []), [])

    def test_ajax_invalid_dataset_is_noop_with_json_shape(self):
        """Invalid app/name keeps cart unchanged and still returns expected JSON keys."""
        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=None):
            response = self.client.post(
                self.url,
                data={'app': 'warehouse', 'name': 'missing', 'title': 'Missing'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload.keys()), {'success', 'in_cart', 'cart_count'})
        self.assertTrue(payload['success'])
        self.assertFalse(payload['in_cart'])
        self.assertEqual(payload['cart_count'], 0)
        self.assertEqual(self.client.session.get('cart', []), [])

    def test_ajax_add_when_cart_is_full_keeps_item_out_of_cart(self):
        """Overflow adds report the unchanged state instead of a false in-cart toggle."""
        session = self.client.session
        session['cart'] = [
            {'app': 'warehouse', 'name': f'ds-{i}', 'title': f'Dataset {i}'}
            for i in range(CART_MAX_ITEMS)
        ]
        session.save()

        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            response = self.client.post(
                self.url,
                data={'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertFalse(payload['in_cart'])
        self.assertEqual(payload['cart_count'], CART_MAX_ITEMS)
        self.assertEqual(len(self.client.session.get('cart', [])), CART_MAX_ITEMS)

    def test_open_redirect_prevented(self):
        """POST with external next URL redirects to / instead."""
        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            response = self.client.post(
                self.url,
                data={
                    'app': 'warehouse',
                    'name': 'dataset-1',
                    'title': 'Dataset 1',
                    'next': 'https://evil.com/steal',
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

    def test_safe_next_redirect(self):
        """POST with safe next URL redirects to it."""
        with mock.patch('ticketing.views.resolve_cart_dataset', return_value=self._dataset()):
            response = self.client.post(
                self.url,
                data={
                    'app': 'warehouse',
                    'name': 'dataset-1',
                    'title': 'Dataset 1',
                    'next': '/cart/',
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/cart/')


class CartIdentityTest(TestCase):
    """Regression tests for app-aware cart item identity."""

    databases = {'default', 'auth_db'}

    def test_duplicate_dataset_names_from_different_apps_do_not_collide(self):
        """Name-only duplicates remain independently selectable by source app."""
        session = self.client.session

        self.assertTrue(CartService.add(session, 'warehouse', 'shared-name', 'Warehouse Dataset'))
        self.assertTrue(
            CartService.add(session, 'fair_genomes', 'shared-name', 'FAIR Genomes Dataset')
        )

        self.assertEqual(
            CartService.item_keys(session),
            {'warehouse/shared-name', 'fair_genomes/shared-name'},
        )
        self.assertTrue(CartService.contains(session, 'warehouse', 'shared-name'))
        self.assertTrue(CartService.contains(session, 'fair_genomes', 'shared-name'))

        self.assertTrue(CartService.remove(session, 'warehouse', 'shared-name'))
        self.assertFalse(CartService.contains(session, 'warehouse', 'shared-name'))
        self.assertTrue(CartService.contains(session, 'fair_genomes', 'shared-name'))


class CartSubmissionViewTest(TestCase):
    """Regression tests for creating tickets from empty and non-empty carts."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='submit-user',
            email='submit@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)
        self.cart_url = reverse('ticketing:cart')
        self.history_url = reverse('ticketing:ticket_history')

    def test_empty_cart_submit_succeeds_with_description(self):
        """Description-only requests create a ticket without item rows."""
        with mock.patch(
            'ticketing.services.ticketing_service.get_ticket_service',
            return_value=StaticTicketBackend(),
        ):
            response = self.client.post(
                self.cart_url,
                data={'description': 'Please help me identify the right dataset.'},
            )

        self.assertRedirects(response, self.history_url, fetch_redirect_response=False)
        ticket = TicketRequest.objects.get()
        self.assertEqual(ticket.description, 'Please help me identify the right dataset.')
        self.assertEqual(ticket.status, TicketRequest.Status.SUBMITTED)
        self.assertEqual(ticket.item_count, 0)
        self.assertEqual(TicketRequestItem.objects.count(), 0)

    def test_empty_cart_ticket_history_displays_zero_items_and_no_items(self):
        """History renders description-only tickets with zero items and empty item text."""
        TicketRequest.objects.create(
            requester=self.user,
            requester_email=self.user.email,
            requester_name=self.user.username,
            subject='Data access request',
            description='Description-only request',
            status=TicketRequest.Status.SUBMITTED,
        )

        response = self.client.get(self.history_url, HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['tickets'][0].item_count, 0)
        self.assertContains(response, 'Data access request')
        self.assertContains(response, 'Description-only request')
        self.assertContains(response, 'No items')

    def test_history_excludes_failed_local_requests(self):
        """History only lists requests that were submitted to the external ticketing system."""
        TicketRequest.objects.create(
            requester=self.user,
            requester_email=self.user.email,
            requester_name=self.user.username,
            subject='Failed request',
            description='This was not created in ALVAO.',
            status=TicketRequest.Status.FAILED,
        )
        TicketRequest.objects.create(
            requester=self.user,
            requester_email=self.user.email,
            requester_name=self.user.username,
            subject='Submitted request',
            description='This exists in ALVAO.',
            status=TicketRequest.Status.SUBMITTED,
        )

        response = self.client.get(self.history_url, HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(len(response.context['tickets']), 1)
        self.assertContains(response, 'Submitted request')
        self.assertNotContains(response, 'Failed request')

    def test_non_empty_cart_submit_creates_item_rows(self):
        """Submitting selected datasets still persists requested item rows."""
        session = self.client.session
        session['cart'] = [
            {'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'},
            {'app': 'fair_genomes', 'name': 'dataset-2', 'title': 'Dataset 2'},
        ]
        session.save()

        with mock.patch(
            'ticketing.services.ticketing_service.get_ticket_service',
            return_value=StaticTicketBackend(),
        ):
            response = self.client.post(
                self.cart_url,
                data={'description': 'Access to selected datasets.'},
            )

        self.assertRedirects(response, self.history_url, fetch_redirect_response=False)
        ticket = TicketRequest.objects.get()
        self.assertEqual(ticket.item_count, 2)
        self.assertEqual(
            set(TicketRequestItem.objects.values_list('item_id', flat=True)),
            {'warehouse/dataset-1', 'fair_genomes/dataset-2'},
        )
        self.assertEqual(self.client.session.get('cart', []), [])

    def test_failed_submit_deletes_local_draft_and_keeps_cart(self):
        """Failed external submission leaves no local history row and keeps selected items."""
        session = self.client.session
        session['cart'] = [{'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'}]
        session.save()

        with mock.patch(
            'ticketing.services.ticketing_service.get_ticket_service',
            return_value=FailingTicketBackend(),
        ):
            response = self.client.post(
                self.cart_url,
                data={'description': 'Access to selected datasets.'},
                follow=True,
            )

        self.assertRedirects(response, self.cart_url)
        self.assertEqual(TicketRequest.objects.count(), 0)
        self.assertEqual(TicketRequestItem.objects.count(), 0)
        self.assertEqual(self.client.session.get('cart', []), session['cart'])
        response_messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any('DWH' in m for m in response_messages))


class TicketingServiceSubmitTest(TestCase):
    """Regression tests for TicketingService requester mapping."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='mock-user',
            email='mock-user@example.com',
            password='secret123',
            first_name='Mock',
            last_name='User',
        )
        self.ticket = TicketRequest.objects.create(
            requester=self.user,
            requester_email=self.user.email,
            requester_name=self.user.get_full_name(),
            subject='Data access request',
            description='Need access.',
        )

    def test_submit_ticket_omits_requester_when_ldap_is_mocked_without_test_email(self):
        """Mock LDAP lets AlvaoService fall back to the service account when no test email is set."""
        backend = CapturingTicketBackend()

        with (
            self.settings(
                MOCK_LDAP=True,
                ALVAO_SERVICE_ACCOUNT_USERNAME='SR_Alvao_Servicedesk_DWH',
                ALVAO_TEST_REQUESTER_EMAIL='',
                ALVAO_TEST_REQUESTER_NAME='',
            ),
            mock.patch(
                'ticketing.services.ticketing_service.get_ticket_service',
                return_value=backend,
            ),
        ):
            TicketingService.submit_ticket(self.ticket, [])

        self.assertEqual(backend.ticket_data.requester_email, '')
        self.assertEqual(backend.ticket_data.requester_name, '')
        self.assertEqual(backend.ticket_data.requester_username, '')
        self.assertNotIn('requester', backend.ticket_data.to_dict())

    def test_submit_ticket_uses_test_requester_email_when_ldap_is_mocked(self):
        """Mock LDAP can exercise the real Alvao requester lookup by test email."""
        backend = CapturingTicketBackend()

        with (
            self.settings(
                MOCK_LDAP=True,
                ALVAO_SERVICE_ACCOUNT_USERNAME='SR_Alvao_Servicedesk_DWH',
                ALVAO_TEST_REQUESTER_EMAIL='real.alvao.user@example.com',
                ALVAO_TEST_REQUESTER_NAME='Real Alvao User',
            ),
            mock.patch(
                'ticketing.services.ticketing_service.get_ticket_service',
                return_value=backend,
            ),
        ):
            TicketingService.submit_ticket(self.ticket, [])

        self.assertEqual(backend.ticket_data.requester_email, 'real.alvao.user@example.com')
        self.assertEqual(backend.ticket_data.requester_name, 'Real Alvao User')
        self.assertEqual(backend.ticket_data.requester_username, '')
        self.assertEqual(
            backend.ticket_data.to_dict()['requester'],
            {'email': 'real.alvao.user@example.com', 'name': 'Real Alvao User'},
        )

    def test_submit_ticket_keeps_requester_when_ldap_is_real(self):
        """Real LDAP users are still sent as Alvao requesters."""
        backend = CapturingTicketBackend()

        with (
            self.settings(
                MOCK_LDAP=False,
                ALVAO_TEST_REQUESTER_EMAIL='ignored@example.com',
            ),
            mock.patch(
                'ticketing.services.ticketing_service.get_ticket_service',
                return_value=backend,
            ),
        ):
            TicketingService.submit_ticket(self.ticket, [])

        self.assertEqual(backend.ticket_data.requester_email, self.user.email)
        self.assertEqual(backend.ticket_data.requester_name, 'Mock User')
        self.assertEqual(backend.ticket_data.requester_username, self.user.username)
        self.assertEqual(backend.ticket_data.to_dict()['requester']['email'], self.user.email)


class CartOverflowTest(TestCase):
    """Tests for the cart item limit (CART_MAX_ITEMS)."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='overflow-user',
            email='overflow@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)

    def test_cart_rejects_item_beyond_max(self):
        """Adding an item when the cart is full returns False."""
        session = self.client.session
        session['cart'] = [
            {'app': 'warehouse', 'name': f'ds-{i}', 'title': f'Dataset {i}'}
            for i in range(CART_MAX_ITEMS)
        ]
        session.save()

        # Re-fetch session after save to get the persisted state
        result = CartService.add(self.client.session, 'warehouse', 'ds-overflow', 'Overflow')
        self.assertFalse(result)

    def test_cart_accepts_item_at_boundary(self):
        """Adding an item when cart has MAX-1 items succeeds."""
        session = self.client.session
        session['cart'] = [
            {'app': 'warehouse', 'name': f'ds-{i}', 'title': f'Dataset {i}'}
            for i in range(CART_MAX_ITEMS - 1)
        ]
        session.save()

        result = CartService.add(self.client.session, 'warehouse', 'ds-last', 'Last One')
        self.assertTrue(result)

    def test_toggle_returns_false_when_cart_is_full(self):
        """Toggle reports failure when it cannot add a new item."""
        session = self.client.session
        session['cart'] = [
            {'app': 'warehouse', 'name': f'ds-{i}', 'title': f'Dataset {i}'}
            for i in range(CART_MAX_ITEMS)
        ]
        session.save()

        result = CartService.toggle(self.client.session, 'warehouse', 'ds-overflow', 'Overflow')

        self.assertFalse(result)
        self.assertEqual(len(self.client.session.get('cart', [])), CART_MAX_ITEMS)
