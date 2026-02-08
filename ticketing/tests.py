"""
Tests for the ticketing application.

Covers models, forms, views, services, and cart functionality.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from .forms import TicketSubmitForm
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


class TicketSubmitFormTest(TestCase):
    """Tests for the TicketSubmitForm."""

    def test_valid_form(self):
        """Form with required fields is valid."""
        form = TicketSubmitForm(
            data={
                'subject': 'Test Subject',
                'description': 'Test description',
            }
        )
        self.assertTrue(form.is_valid())

    def test_subject_required(self):
        """Subject field is required."""
        form = TicketSubmitForm(
            data={
                'description': 'Test description',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('subject', form.errors)

    def test_description_optional(self):
        """Description field is optional."""
        form = TicketSubmitForm(
            data={
                'subject': 'Test Subject',
            }
        )
        self.assertTrue(form.is_valid())

    def test_subject_max_length(self):
        """Subject has max length of 500."""
        form = TicketSubmitForm(
            data={
                'subject': 'A' * 501,
            }
        )
        self.assertFalse(form.is_valid())


class TicketDataTest(TestCase):
    """Tests for the TicketData dataclass."""

    def test_to_dict(self):
        """to_dict converts to API payload format."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
            requester_name='Test User',
        )
        result = data.to_dict()
        self.assertEqual(result['subject'], 'Test')
        self.assertEqual(result['description'], 'Desc')
        self.assertEqual(result['requesterEmail'], 'test@example.com')
        self.assertEqual(result['requesterName'], 'Test User')

    def test_to_dict_minimal(self):
        """to_dict with only required fields."""
        data = TicketData(
            subject='Test',
            description='Desc',
            requester_email='test@example.com',
        )
        result = data.to_dict()
        self.assertIn('subject', result)
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
        """from_dict creates instance from API response."""
        response = TicketResponse.from_dict(
            {
                'ticketId': '123',
                'ticketNumber': 'T-123',
                'status': 'New',
                'url': 'http://example.com/ticket/123',
            }
        )
        self.assertEqual(response.ticket_id, '123')
        self.assertEqual(response.ticket_number, 'T-123')
        self.assertEqual(response.status, 'New')

    def test_from_dict_with_alternative_keys(self):
        """from_dict handles alternative key names."""
        response = TicketResponse.from_dict(
            {
                'id': '456',
                'number': 'T-456',
                'state': 'Open',
            }
        )
        self.assertEqual(response.ticket_id, '456')
        self.assertEqual(response.ticket_number, 'T-456')
        self.assertEqual(response.status, 'Open')


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
        """Factory returns MockAlvaoService when ALVAO_USE_MOCK is True."""
        with self.settings(ALVAO_USE_MOCK=True):
            service = get_ticket_service()
            self.assertIsInstance(service, MockAlvaoService)

    def test_returns_alvao_when_not_mock(self):
        """Factory returns AlvaoService when ALVAO_USE_MOCK is False."""
        with self.settings(ALVAO_USE_MOCK=False):
            from .services.alvao_service import AlvaoService

            service = get_ticket_service()
            self.assertIsInstance(service, AlvaoService)


class CartViewTest(TestCase):
    """Tests for cart-related views."""

    databases = {'default', 'auth_db'}

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )

    def test_cart_view_redirects_unauthenticated(self):
        """Cart view redirects unauthenticated users."""
        from .views import CartView

        request = self.factory.get('/ticketing/cart/')
        request.user = AnonymousUser()
        response = CartView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_add_to_cart_redirects_unauthenticated(self):
        """Add to cart redirects unauthenticated users."""
        from .views import AddToCartView

        request = self.factory.post('/ticketing/cart/add/')
        request.user = AnonymousUser()
        response = AddToCartView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_clear_cart_redirects_unauthenticated(self):
        """Clear cart redirects unauthenticated users."""
        from .views import ClearCartView

        request = self.factory.post('/ticketing/cart/clear/')
        request.user = AnonymousUser()
        response = ClearCartView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_my_tickets_redirects_unauthenticated(self):
        """My tickets view redirects unauthenticated users."""
        from .views import MyTicketsView

        request = self.factory.get('/ticketing/my-tickets/')
        request.user = AnonymousUser()
        response = MyTicketsView.as_view()(request)
        self.assertEqual(response.status_code, 302)
