"""Ticket persistence and submission workflows."""

from __future__ import annotations

import contextlib
import logging

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ticketing.models import TicketRequest, TicketRequestItem
from ticketing.presenters import (
    build_ticket_description,
    build_ticket_history_entries,
    build_ticket_subject,
)
from ticketing.read_models import TicketHistoryEntry
from ticketing.services.base import TicketData
from ticketing.services.factory import get_ticket_service

logger = logging.getLogger(__name__)


class TicketingService:
    """High-level service for creating and submitting ticket requests."""

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
        auto_subject = build_ticket_subject(cart, str(_('Data access request')))

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

    @staticmethod
    def submit_ticket(ticket: TicketRequest, cart: list[dict]) -> str | None:
        """Submit *ticket* to the external ticketing system (Alvao).

        On success, updates the ticket status to ``SUBMITTED`` and returns the
        external ticket ID. On failure, deletes the local draft and re-raises
        the exception so history only contains tickets that exist externally.
        """
        try:
            requester_email = ticket.requester_email
            requester_name = ticket.requester_name
            requester_username = (
                getattr(ticket.requester, 'username', '') if ticket.requester else ''
            )
            if getattr(settings, 'MOCK_LDAP', False):
                requester_email = ''
                requester_name = ''
                requester_username = getattr(settings, 'ALVAO_SERVICE_ACCOUNT_USERNAME', '')

            service = get_ticket_service()
            ticket_data = TicketData(
                subject=ticket.subject,
                description=build_ticket_description(ticket.description, cart),
                requester_email=requester_email,
                requester_name=requester_name,
                requester_username=requester_username,
            )
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
            ticket_pk = ticket.pk
            logger.exception(
                'Ticket submission failed for ticket pk=%s user=%s',
                ticket_pk,
                ticket.requester,
            )
            with contextlib.suppress(Exception):
                ticket.delete()
                logger.info(
                    'Deleted failed local TicketRequest after Alvao submission failure: pk=%s',
                    ticket_pk,
                )
            raise

    @staticmethod
    def get_user_tickets(user) -> list[TicketHistoryEntry]:
        """Return read models for tickets belonging to *user*."""
        tickets = list(
            TicketRequest.objects.filter(
                models.Q(requester=user)
                | models.Q(requester__isnull=True, requester_email=user.email)
            )
            .filter(status__in=[TicketRequest.Status.SUBMITTED, TicketRequest.Status.CONFIRMED])
            .prefetch_related('items')
            .order_by('-created_at')
        )
        return build_ticket_history_entries(tickets)
