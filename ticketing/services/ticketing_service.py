"""
Ticketing Service — orchestrates ticket creation, item persistence,
and external ticketing system submission.

All direct ORM access for the ticketing domain lives here so that views
remain free of database calls.
"""

from __future__ import annotations

import logging

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ticketing.models import TicketRequest, TicketRequestItem
from ticketing.services.base import TicketData
from ticketing.services.factory import get_ticket_service

logger = logging.getLogger(__name__)


class TicketingService:
    """High-level service for creating and submitting ticket requests."""

    # ── Ticket creation ─────────────────────────────────────────────────────

    @staticmethod
    def create_ticket_from_cart(
        user,
        description: str,
        cart: list[dict],
        session_key: str | None,
    ) -> TicketRequest:
        """Create a ``TicketRequest`` with items from *cart* in a single transaction.

        Returns the persisted ``TicketRequest`` in ``DRAFT`` status.
        """
        dataset_names = ', '.join(item['title'] for item in cart)
        auto_subject = (
            (str(_('Data access request')) + f' \u2014 {dataset_names}')
            if dataset_names
            else str(_('Data access request'))
        )[:500]

        with transaction.atomic():
            ticket = TicketRequest.objects.create(
                requester=user,
                requester_email=user.email,
                requester_name=user.get_full_name() or user.username,
                subject=auto_subject,
                description=description,
                status=TicketRequest.Status.DRAFT,
                session_key=session_key,
            )
            for item in cart:
                TicketRequestItem.objects.create(
                    ticket_request=ticket,
                    item_type=TicketRequestItem.ItemType.DATASET,
                    item_id=f'{item["app"]}/{item["name"]}',
                    item_name=item['title'],
                    parent_dataset=item['name'],
                )

        logger.info(
            'TicketRequest created: pk=%s user=%s items=%d',
            ticket.pk,
            user,
            len(cart),
        )
        return ticket

    # ── Alvao submission ────────────────────────────────────────────────────

    @staticmethod
    def submit_ticket(ticket: TicketRequest, cart: list[dict]) -> str | None:
        """Submit *ticket* to the external ticketing system (Alvao).

        On success, updates the ticket status to ``SUBMITTED`` and returns the
        external ticket ID.  On failure, marks the ticket as ``FAILED`` and
        re-raises the exception.
        """
        service = get_ticket_service()
        ticket_data = TicketData(
            subject=ticket.subject,
            description=_build_ticket_description(ticket, cart),
            requester_email=ticket.requester_email,
            requester_name=ticket.requester_name,
        )
        try:
            response = service.create_ticket(ticket_data)
            ticket.alvao_ticket_id = response.ticket_id
            ticket.status = TicketRequest.Status.SUBMITTED
            ticket.submitted_at = timezone.now()
            ticket.save()
            logger.info(
                'Ticket submitted to Alvao: local_pk=%s alvao_id=%s user=%s',
                ticket.pk,
                response.ticket_id,
                ticket.requester,
            )
            return response.ticket_id
        except Exception:
            logger.exception(
                'Ticket submission failed for ticket pk=%s user=%s',
                ticket.pk,
                ticket.requester,
            )
            ticket.status = TicketRequest.Status.FAILED
            ticket.save()
            raise

    # ── Queries ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_user_tickets(user):
        """Return a QuerySet of tickets belonging to *user* (including pre-auth sessions)."""
        return (
            TicketRequest.objects.filter(
                models.Q(requester=user)
                | models.Q(requester__isnull=True, requester_email=user.email)
            )
            .prefetch_related('items')
            .order_by('-created_at')
        )


def _build_ticket_description(ticket: TicketRequest, cart: list[dict]) -> str:
    lines = [ticket.description]
    if cart:
        lines += ['', '--- Requested datasets ---']
        for item in cart:
            lines.append(f'  [{item["app"]}] {item["title"]} ({item["name"]})')
    return '\n'.join(lines)
