"""
Tests for the ticketing application.

Covers models, forms, views, services, and cart functionality.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ticketing.cart import CART_MAX_ITEMS, CartService

from .models import TicketRequest, TicketRequestItem
from .services.base import TicketData, TicketResponse
from .services.factory import get_ticket_service
from .services.mock_service import MockAlvaoService


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
        from django.db import IntegrityError

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
        self.assertIn('priority', result)
        self.assertNotIn('serviceId', result)
        self.assertNotIn('slaId', result)

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
            from .services.alvao_service import AlvaoService

            service = get_ticket_service()
            self.assertIsInstance(service, AlvaoService)


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

    def test_ajax_add_stores_item_and_returns_count(self):
        """AJAX add stores the cart item and reports in_cart/count."""
        response = self.client.post(
            self.url,
            data={'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'},
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
        self.assertEqual(cart[0]['title'], 'Dataset 1')

    def test_ajax_toggle_same_item_removes_from_cart(self):
        """Posting the same item twice toggles it out of the cart."""
        data = {'app': 'warehouse', 'name': 'dataset-1', 'title': 'Dataset 1'}

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

    def test_open_redirect_prevented(self):
        """POST with external next URL redirects to / instead."""
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
