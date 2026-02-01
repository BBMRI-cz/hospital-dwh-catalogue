"""
Service factory for getting the appropriate ticket service based on environment.
"""
import logging
from typing import Optional, Union

from django.conf import settings

from .alvao_service import AlvaoService
from .mock_service import MockAlvaoService


logger = logging.getLogger(__name__)

# Type alias for ticket services
TicketService = Union[AlvaoService, MockAlvaoService]


def get_ticket_service() -> TicketService:
    """
    Get the appropriate ticket service based on configuration.
    
    Returns:
        - MockAlvaoService if ALVAO_USE_MOCK is True (dev environment)
        - AlvaoService for production/test environments
    """
    use_mock = getattr(settings, 'ALVAO_USE_MOCK', False)
    
    if use_mock:
        logger.info("Using mock Alvao service (ALVAO_USE_MOCK=True)")
        return MockAlvaoService(use_database=True)
    
    logger.info("Using real Alvao service")
    return AlvaoService()


class TicketServiceManager:
    """
    Context manager for ticket service operations.
    
    Usage:
        with TicketServiceManager() as service:
            response = service.create_ticket(ticket_data)
    """
    
    def __init__(self, service: Optional[TicketService] = None):
        """
        Initialize with optional explicit service.
        
        Args:
            service: Specific service to use, or None to auto-detect
        """
        self._service = service
        self._should_close = False
    
    def __enter__(self) -> TicketService:
        if self._service is None:
            self._service = get_ticket_service()
            self._should_close = True
        return self._service
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._should_close and self._service is not None and hasattr(self._service, 'close'):
            self._service.close()  # type: ignore[union-attr]
