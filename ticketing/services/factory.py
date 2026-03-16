"""
Service factory for getting the appropriate ticket service based on environment.
"""

import logging

from django.conf import settings

from .alvao_service import AlvaoService
from .mock_service import MockAlvaoService

logger = logging.getLogger(__name__)

# Type alias for ticket services
TicketService = AlvaoService | MockAlvaoService


def get_ticket_service() -> TicketService:
    """
    Get the appropriate ticket service based on configuration.

    Returns:
        - MockAlvaoService if MOCK_ALVAO is True (dev environment)
        - AlvaoService for production/test environments
    """
    use_mock = getattr(settings, 'MOCK_ALVAO', False)

    if use_mock:
        logger.info('Using mock Alvao service (MOCK_ALVAO=True)')
        return MockAlvaoService(use_database=True)

    logger.info('Using real Alvao service')
    return AlvaoService()

