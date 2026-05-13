"""
Data structures for ticket services.

Defines common data types used by both the real Alvao service and the mock service.
Uses Alvao REST API v1.3 field naming conventions.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from html import escape
from typing import Any


class AlvaoPriority(StrEnum):
    """Alvao ticket priority levels."""

    PLANNING = 'Planning'
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'
    CRITICAL = 'Critical'


class AlvaoImpact(StrEnum):
    """Alvao ticket impact levels."""

    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'


class AlvaoUrgency(StrEnum):
    """Alvao ticket urgency levels."""

    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'


def _plain_to_html(text: str) -> str:
    """Convert plain text to safe HTML, preserving line breaks."""
    return escape(text).replace('\n', '<br>')


@dataclass
class TicketData:
    """Data structure for creating a ticket via Alvao POST /tickets."""

    subject: str
    description: str
    requester_email: str = ''
    requester_name: str = ''
    requester_username: str = ''
    requester_id: int | None = None
    requester_lookup_source: str = ''
    service_id: int | None = None
    priority: AlvaoPriority | None = None
    impact: AlvaoImpact | None = None
    urgency: AlvaoUrgency | None = None
    custom_items: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to Alvao REST API v1.3 payload for SD.CreateTicketRequest."""
        data: dict[str, Any] = {
            'name': self.subject,
            'descriptionHtml': _plain_to_html(self.description),
        }
        if self.requester_id:
            data['requester'] = {'id': self.requester_id}
        elif self.requester_email:
            requester: dict[str, Any] = {'email': self.requester_email}
            if self.requester_name:
                requester['name'] = self.requester_name
            data['requester'] = requester
        if self.priority:
            data['priority'] = str(self.priority)
        if self.service_id:
            data['serviceId'] = self.service_id
        if self.impact:
            data['impact'] = str(self.impact)
        if self.urgency:
            data['urgency'] = str(self.urgency)
        if self.custom_items:
            data['customItems'] = self.custom_items
        return data


@dataclass
class TicketResponse:
    """Response data from ticket creation (Alvao SD.Ticket schema)."""

    ticket_id: str
    ticket_number: str | None = None
    status: str | None = None
    url: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'TicketResponse':
        """Create TicketResponse from Alvao API response.

        Alvao returns SD.Ticket with fields:
          id (int), messageTag (str, e.g. 'T137SD'),
          stateName (str, e.g. 'New'), _links.self.href (str).
        """
        links = data.get('_links', {})
        self_href = links.get('self', {}).get('href') if isinstance(links, dict) else None

        return cls(
            ticket_id=str(data.get('id', '')),
            ticket_number=data.get('messageTag'),
            status=data.get('stateName'),
            url=self_href,
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
