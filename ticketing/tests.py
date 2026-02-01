"""
Tests for the ticketing application.
"""
from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, RequestFactory
from django.urls import reverse

from .forms import TicketSubmitForm
from .models import TicketRequest, TicketRequestItem
from .services.base import TicketData, TicketResponse
from .services.mock_service import MockAlvaoService
from .services.alvao_service import AlvaoServiceException


class TicketRequestModelTest(TestCase):
    """Test cases for TicketRequest model."""
    
    def test_str_with_alvao_id(self):
        """Test string representation with Alvao ticket ID."""
        ticket = TicketRequest(
            alvao_ticket_id='T-12345',
            subject='Test Request'
        )
        self.assertIn('T-12345', str(ticket))
    
    def test_str_without_alvao_id(self):
        """Test string representation without Alvao ticket ID."""
        ticket = TicketRequest(subject='Test Request')
        self.assertIn('Draft', str(ticket))
    
    def test_is_submitted_draft(self):
        """Test is_submitted returns False for draft."""
        ticket = TicketRequest(status=TicketRequest.Status.DRAFT)
        self.assertFalse(ticket.is_submitted)
    
    def test_is_submitted_submitted(self):
        """Test is_submitted returns True for submitted."""
        ticket = TicketRequest(status=TicketRequest.Status.SUBMITTED)
        self.assertTrue(ticket.is_submitted)


class TicketRequestItemModelTest(TestCase):
    """Test cases for TicketRequestItem model."""
    
    def setUp(self):
        """Set up test data."""
        self.ticket = TicketRequest.objects.create(
            subject='Test',
            requester_email='test@example.com'
        )
    
    def test_str_representation(self):
        """Test string representation."""
        item = TicketRequestItem(
            ticket_request=self.ticket,
            item_type=TicketRequestItem.ItemType.DATASET,
            item_id='DS001',
            item_name='Test Dataset'
        )
        self.assertIn('Test Dataset', str(item))


class TicketSubmitFormTest(TestCase):
    """Test cases for TicketSubmitForm."""
    
    def test_valid_form(self):
        """Test form with valid data."""
        form = TicketSubmitForm(data={
            'requester_email': 'test@example.com',
            'requester_name': 'Test User',
            'subject': 'Test Request',
            'description': 'Test description'
        })
        self.assertTrue(form.is_valid())
    
    def test_email_normalization(self):
        """Test email is normalized to lowercase."""
        form = TicketSubmitForm(data={
            'requester_email': 'TEST@EXAMPLE.COM',
            'subject': 'Test'
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['requester_email'], 'test@example.com')
    
    def test_invalid_email(self):
        """Test form rejects invalid email."""
        form = TicketSubmitForm(data={
            'requester_email': 'not-an-email',
            'subject': 'Test'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('requester_email', form.errors)


class MockAlvaoServiceTest(TestCase):
    """Test cases for MockAlvaoService."""
    
    def setUp(self):
        """Set up test service."""
        MockAlvaoService.clear_storage()
        self.service = MockAlvaoService(use_database=False)
    
    def test_create_ticket(self):
        """Test creating a mock ticket."""
        ticket_data = TicketData(
            subject='Test Ticket',
            description='Test description',
            requester_email='test@example.com',
            requester_name='Test User'
        )
        
        response = self.service.create_ticket(ticket_data)
        
        self.assertIsNotNone(response.ticket_id)
        self.assertTrue(response.ticket_id.startswith('MOCK-'))
        self.assertEqual(response.status, 'New')
    
    def test_get_ticket(self):
        """Test retrieving a mock ticket."""
        # First create a ticket
        ticket_data = TicketData(
            subject='Test Ticket',
            description='Test description',
            requester_email='test@example.com'
        )
        created = self.service.create_ticket(ticket_data)
        
        # Then retrieve it
        retrieved = self.service.get_ticket(created.ticket_id)
        
        self.assertEqual(retrieved.ticket_id, created.ticket_id)
        self.assertEqual(retrieved.subject, 'Test Ticket')
    
    def test_get_nonexistent_ticket(self):
        """Test retrieving a nonexistent ticket."""
        with self.assertRaises(AlvaoServiceException) as context:
            self.service.get_ticket('NONEXISTENT')
        
        self.assertEqual(context.exception.status_code, 404)
    
    def test_get_tickets_by_requester(self):
        """Test getting tickets by requester email."""
        # Create some tickets
        for i in range(3):
            self.service.create_ticket(TicketData(
                subject=f'Ticket {i}',
                description='Test',
                requester_email='user@example.com'
            ))
        
        # Create one for different user
        self.service.create_ticket(TicketData(
            subject='Other Ticket',
            description='Test',
            requester_email='other@example.com'
        ))
        
        # Get tickets for first user
        tickets = self.service.get_tickets_by_requester('user@example.com')
        
        self.assertEqual(len(tickets), 3)
    
    def test_health_check(self):
        """Test health check returns True."""
        self.assertTrue(self.service.health_check())


class CartViewTest(TestCase):
    """Test cases for cart views."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_cart_view(self):
        """Test cart view returns 200."""
        response = self.client.get(reverse('ticketing:cart'))
        self.assertEqual(response.status_code, 200)
    
    def test_cart_count_empty(self):
        """Test cart count returns 0 for empty cart."""
        response = self.client.get(reverse('ticketing:cart_count'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)
    
    @patch('ticketing.views.get_object_or_404')
    def test_add_to_cart(self, mock_get):
        """Test adding item to cart."""
        # Mock the warehouse model
        mock_dataset = MagicMock()
        mock_dataset.display_name = 'Test Dataset'
        mock_dataset.description = 'Test description'
        mock_get.return_value = mock_dataset
        
        response = self.client.post(
            reverse('ticketing:add_to_cart'),
            {'item_type': 'dataset', 'item_id': 'DS001'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'added')
        self.assertEqual(data['cart_count'], 1)
    
    @patch('ticketing.views.get_object_or_404')
    def test_toggle_cart_removes_item(self, mock_get):
        """Test that clicking add on existing item removes it."""
        # Mock the warehouse model
        mock_dataset = MagicMock()
        mock_dataset.display_name = 'Test Dataset'
        mock_dataset.description = 'Test description'
        mock_get.return_value = mock_dataset
        
        # Add item first
        self.client.post(
            reverse('ticketing:add_to_cart'),
            {'item_type': 'dataset', 'item_id': 'DS001'}
        )
        
        # Toggle (should remove)
        response = self.client.post(
            reverse('ticketing:add_to_cart'),
            {'item_type': 'dataset', 'item_id': 'DS001'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'removed')
        self.assertEqual(data['cart_count'], 0)
    
    def test_add_to_cart_missing_params(self):
        """Test add to cart with missing parameters."""
        response = self.client.post(reverse('ticketing:add_to_cart'), {})
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
    
    def test_cart_items(self):
        """Test cart items endpoint returns item list."""
        response = self.client.get(reverse('ticketing:cart_items'))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('items', data)
        self.assertIn('count', data)
        self.assertEqual(data['count'], 0)
    
    def test_clear_cart(self):
        """Test clearing the cart."""
        response = self.client.post(reverse('ticketing:clear_cart'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['cart_count'], 0)
