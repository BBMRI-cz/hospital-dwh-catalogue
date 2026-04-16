"""Ticket service selection."""

import logging

from django.conf import settings

from .alvao_service import AlvaoService
from .mock_service import MockAlvaoService

logger = logging.getLogger(__name__)

TicketService = AlvaoService | MockAlvaoService


def get_ticket_service() -> TicketService:
    """Return the configured ticket service implementation."""
    use_mock = getattr(settings, 'MOCK_ALVAO', False)

    if use_mock:
        logger.info('Using mock Alvao service (MOCK_ALVAO=True)')
        return MockAlvaoService(use_database=True)

    logger.info('Using real Alvao service')
    return AlvaoService()
