"""
Mock Alvao Service for development environment.

This service simulates Alvao Service Desk API behavior without making real API calls.
Stores tickets in a local SQLite database or in-memory for testing.
"""

import logging
import uuid
from datetime import datetime

from django.utils import timezone

from .alvao_service import AlvaoServiceException
from .base import TicketData, TicketInfo, TicketResponse

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
            'ticketId': ticket_id,
            'ticketNumber': ticket_number,
            'subject': ticket_data.subject,
            'description': ticket_data.description,
            'requesterEmail': ticket_data.requester_email,
            'requesterName': ticket_data.requester_name,
            'status': 'New',
            'createdAt': now,
            'updatedAt': now,
            'url': f'http://localhost:8000/ticketing/mock-ticket/{ticket_id}/',
            'serviceId': ticket_data.service_id,
            'customFields': ticket_data.custom_fields,
        }

        self._store_ticket(ticket_id, stored_data)

        logger.info(f'[MOCK] Created ticket: {ticket_id} for {ticket_data.requester_email}')

        return TicketResponse(
            ticket_id=ticket_id,
            ticket_number=ticket_number,
            status='New',
            url=stored_data['url'],
            raw_response=stored_data,
        )

    def get_ticket(self, ticket_id: str) -> TicketInfo:
        """
        Get mock ticket information.

        Args:
            ticket_id: The ID of the ticket to retrieve

        Returns:
            TicketInfo with ticket details
        """
        self._simulate_delay()

        stored = self._get_stored_ticket(ticket_id)

        if not stored:
            raise AlvaoServiceException(f'Ticket not found: {ticket_id}', status_code=404)

        return TicketInfo(
            ticket_id=stored['ticketId'],
            ticket_number=stored.get('ticketNumber'),
            subject=stored.get('subject', ''),
            status=stored.get('status', 'Unknown'),
            requester_email=stored.get('requesterEmail', ''),
            created_at=stored.get('createdAt'),
            updated_at=stored.get('updatedAt'),
            url=stored.get('url'),
            raw_response=stored,
        )

    def get_tickets_by_requester(self, requester_email: str) -> list[TicketInfo]:
        """
        Get all mock tickets for a specific requester.

        Args:
            requester_email: Email of the requester

        Returns:
            List of TicketInfo objects
        """
        self._simulate_delay()

        tickets = []

        # Search in memory storage
        for _ticket_id, data in MockAlvaoService._memory_storage.items():
            if data.get('requesterEmail', '').lower() == requester_email.lower():
                tickets.append(
                    TicketInfo(
                        ticket_id=data['ticketId'],
                        ticket_number=data.get('ticketNumber'),
                        subject=data.get('subject', ''),
                        status=data.get('status', 'Unknown'),
                        requester_email=data.get('requesterEmail', ''),
                        created_at=data.get('createdAt'),
                        updated_at=data.get('updatedAt'),
                        url=data.get('url'),
                        raw_response=data,
                    )
                )

        # Also search in database if using it
        if self.use_database:
            from ticketing.models import TicketRequest

            db_tickets = TicketRequest.objects.filter(
                requester_email__iexact=requester_email, alvao_ticket_id__startswith='MOCK-'
            )

            for t in db_tickets:
                # Avoid duplicates
                if not any(ti.ticket_id == t.alvao_ticket_id for ti in tickets):
                    tickets.append(
                        TicketInfo(
                            ticket_id=t.alvao_ticket_id or '',
                            ticket_number=None,
                            subject=t.subject,
                            status=t.status,
                            requester_email=t.requester_email,
                            created_at=t.created_at.isoformat() if t.created_at else None,
                            updated_at=t.updated_at.isoformat() if t.updated_at else None,
                            url=f'http://localhost:8000/ticketing/tickets/{t.pk}/',
                            raw_response=None,
                        )
                    )

        logger.debug(f'[MOCK] Found {len(tickets)} tickets for {requester_email}')

        return tickets

    def health_check(self) -> bool:
        """
        Mock health check - always returns True.

        Returns:
            True if service is "healthy"
        """
        self._simulate_delay()
        return True

    @classmethod
    def clear_storage(cls) -> None:
        """Clear all stored mock tickets. Useful for testing."""
        cls._memory_storage.clear()
        logger.debug('[MOCK] Cleared mock ticket storage')
