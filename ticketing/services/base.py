"""
Data structures for ticket services.

Defines common data types used by both the real Alvao service and the mock service.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TicketData:
    """Data structure for creating a ticket."""

    subject: str
    description: str
    requester_email: str
    requester_name: str = ''
    service_id: int | None = None
    sla_id: int | None = None
    custom_fields: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API payload."""
        data: dict[str, Any] = {
            'subject': self.subject,
            'description': self.description,
            'requesterEmail': self.requester_email,
        }
        if self.requester_name:
            data['requesterName'] = self.requester_name
        if self.service_id:
            data['serviceId'] = self.service_id
        if self.sla_id:
            data['slaId'] = self.sla_id
        if self.custom_fields:
            data['customFields'] = self.custom_fields
        return data


@dataclass
class TicketResponse:
    """Response data from ticket creation."""

    ticket_id: str
    ticket_number: str | None = None
    status: str | None = None
    url: str | None = None
    raw_response: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'TicketResponse':
        """Create TicketResponse from API response dictionary."""
        return cls(
            ticket_id=str(data.get('ticketId', data.get('id', ''))),
            ticket_number=data.get('ticketNumber', data.get('number')),
            status=data.get('status', data.get('state')),
            url=data.get('url', data.get('webUrl')),
            raw_response=data,
        )


@dataclass
class TicketInfo:
    """Information about an existing ticket."""

    ticket_id: str
    ticket_number: str | None = None
    subject: str = ''
    status: str = ''
    requester_email: str = ''
    created_at: str | None = None
    updated_at: str | None = None
    url: str | None = None
    raw_response: dict[str, Any] | None = None
