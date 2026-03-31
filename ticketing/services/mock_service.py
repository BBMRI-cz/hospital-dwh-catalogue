"""
Mock Alvao Service for development environment.

This service simulates Alvao Service Desk API behavior without making real API calls.
Stores tickets in a local SQLite database or in-memory for testing.
"""

import logging
import uuid
from datetime import datetime

from django.utils import timezone

from .base import TicketData, TicketResponse

logger = logging.getLogger(__name__)


class MockAlvaoService:
    """
    Mock implementation of Alvao Service Desk API.

    Used in development environment to simulate ticket creation and retrieval
    without connecting to a real Alvao server.

    Tickets are stored in the local database using the MockTicket model.
    """

    # In-memory storage for tickets (used when database is not available)
    _memory_storage: dict[str, dict] = {}

    def __init__(self, use_database: bool = True):
        """
        Initialize the mock service.

        Args:
            use_database: Whether to persist to database (vs memory only)
        """
        self.use_database = use_database

    def _simulate_delay(self) -> None:
        """Simulate network delay."""
        import random
        import time

        delay = random.uniform(0.1, 0.5)
        time.sleep(delay)

    def _generate_ticket_id(self) -> str:
        """Generate a mock ticket ID."""
        return f'MOCK-{uuid.uuid4().hex[:8].upper()}'

    def _generate_ticket_number(self) -> str:
        """Generate a mock ticket number."""
        # Simple incrementing number based on timestamp
        return f'T{int(datetime.now().timestamp()) % 100000:05d}'

    def _store_ticket(self, ticket_id: str, data: dict) -> None:
        """Store ticket data (database or memory)."""
        if self.use_database:
            # We store mock tickets in the same model but with mock IDs
            # The actual storage happens through the views
            pass

        # Always store in memory as backup
        MockAlvaoService._memory_storage[ticket_id] = data

    def _get_stored_ticket(self, ticket_id: str) -> dict | None:
        """Retrieve stored ticket data."""
        return MockAlvaoService._memory_storage.get(ticket_id)

    def create_ticket(self, ticket_data: TicketData) -> TicketResponse:
        """
        Create a mock ticket.

        Args:
            ticket_data: Data for the new ticket

        Returns:
            TicketResponse with mock ticket information
        """
        self._simulate_delay()

        ticket_id = self._generate_ticket_id()
        ticket_number = self._generate_ticket_number()
        now = timezone.now().isoformat()

        stored_data = {
            'id': ticket_id,
            'messageTag': ticket_number,
            'name': ticket_data.subject,
            'descriptionHtml': ticket_data.description,
            'requester': {
                'email': ticket_data.requester_email,
                'name': ticket_data.requester_name,
            },
            'stateName': 'New',
            'createdDate': now,
            'serviceId': ticket_data.service_id,
            '_links': {
                'self': {
                    'href': f'http://localhost:8000/ticketing/mock-ticket/{ticket_id}/',
                },
            },
        }

        self._store_ticket(ticket_id, stored_data)

        logger.info(f'[MOCK] Created ticket: {ticket_id} for {ticket_data.requester_email}')

        mock_url = f'http://localhost:8000/ticketing/mock-ticket/{ticket_id}/'

        return TicketResponse(
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            status='New',
            url=mock_url,
            raw_response=stored_data,
        )
