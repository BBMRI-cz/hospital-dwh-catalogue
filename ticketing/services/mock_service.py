"""Mock Alvao service used in non-production environments."""

import logging
import random
import time
import uuid
from datetime import datetime

from django.utils import timezone

from .base import TicketData, TicketResponse

logger = logging.getLogger(__name__)


class MockAlvaoService:
    """Simulate Alvao ticket creation without a live API."""

    _memory_storage: dict[str, dict] = {}

    def __init__(self, use_database: bool = True):
        self.use_database = use_database

    def _simulate_delay(self) -> None:
        """Simulate network delay."""
        delay = random.uniform(0.1, 0.5)
        time.sleep(delay)

    def _generate_ticket_id(self) -> str:
        """Generate a mock ticket ID."""
        return f'MOCK-{uuid.uuid4().hex[:8].upper()}'

    def _generate_ticket_number(self) -> str:
        """Generate a mock ticket number."""
        return f'T{int(datetime.now().timestamp()) % 100000:05d}'

    def _store_ticket(self, ticket_id: str, data: dict) -> None:
        """Store ticket data (database or memory)."""
        if self.use_database:
            pass

        MockAlvaoService._memory_storage[ticket_id] = data

    def _get_stored_ticket(self, ticket_id: str) -> dict | None:
        """Retrieve stored ticket data."""
        return MockAlvaoService._memory_storage.get(ticket_id)

    def create_ticket(self, ticket_data: TicketData) -> TicketResponse:
        """Create and return a mock ticket response."""
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
                'id': ticket_data.requester_id,
                'username': ticket_data.requester_username,
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
