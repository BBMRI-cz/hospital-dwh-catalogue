"""
Alvao Service Desk REST API integration.

This service handles communication with the real Alvao Service Desk API.
Used in production and test environments.
"""

import contextlib
import logging

import requests

from django.conf import settings

from .base import TicketData, TicketInfo, TicketResponse

logger = logging.getLogger(__name__)


class AlvaoServiceException(Exception):
    """Custom exception for Alvao API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AlvaoService:
    """
    Service class for interacting with Alvao Service Desk REST API.

    Alvao REST API documentation:
    - Uses bearer token authentication
    - Base URL typically: https://{server}/api/v1/
    - Main endpoints:
        - POST /tickets - Create a new ticket
        - GET /tickets/{id} - Get ticket details
        - GET /tickets?requester={email} - List tickets by requester

    Usage:
        service = AlvaoService()
        response = service.create_ticket(ticket_data)
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        service_account_username: str | None = None,
        service_account_password: str | None = None,
        default_service_id: int | None = None,
        timeout: int = 30,
    ):
        """
        Initialize the Alvao service.

        Args:
            api_url: Alvao REST API base URL
            api_token: API token for authentication (preferred)
            service_account_username: Username for basic auth (alternative)
            service_account_password: Password for basic auth (alternative)
            default_service_id: Default service ID for new tickets
            timeout: Request timeout in seconds
        """
        self.api_url = (api_url or getattr(settings, 'ALVAO_API_URL', '')).rstrip('/')
        self.api_token = api_token or getattr(settings, 'ALVAO_API_TOKEN', '')
        self.service_account_username = service_account_username or getattr(
            settings, 'ALVAO_SERVICE_ACCOUNT_USERNAME', ''
        )
        self.service_account_password = service_account_password or getattr(
            settings, 'ALVAO_SERVICE_ACCOUNT_PASSWORD', ''
        )
        self.default_service_id = default_service_id or getattr(
            settings, 'ALVAO_DEFAULT_SERVICE_ID', None
        )
        self.timeout = timeout
        self._session: requests.Session | None = None

    @property
    def session(self) -> requests.Session:
        """Lazy-load and reuse requests session with authentication."""
        if self._session is None:
            self._session = requests.Session()

            # Set up headers
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }

            # Prefer token authentication
            if self.api_token:
                headers['Authorization'] = f'Bearer {self.api_token}'

            self._session.headers.update(headers)

            # Fall back to basic auth if no token
            if not self.api_token and self.service_account_username:
                self._session.auth = (self.service_account_username, self.service_account_password)

        return self._session

    def _make_request(
        self, method: str, endpoint: str, data: dict | None = None, params: dict | None = None
    ) -> dict:
        """
        Make an HTTP request to the Alvao API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (relative to base URL)
            data: Request body data (for POST/PUT)
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            AlvaoServiceException: On API or network errors
        """
        url = f'{self.api_url}/{endpoint.lstrip("/")}'

        try:
            logger.debug(f'Alvao API {method} {url}')

            response = self.session.request(
                method=method, url=url, json=data, params=params, timeout=self.timeout
            )

            # Log response for debugging
            logger.debug(f'Alvao API response: {response.status_code}')

            # Check for errors
            if response.status_code >= 400:
                error_data = None
                with contextlib.suppress(Exception):
                    error_data = response.json()

                error_message = f'Alvao API error: {response.status_code}'
                if error_data:
                    error_message = error_data.get('message', error_message)

                logger.error(f'Alvao API error: {response.status_code} - {error_message}')
                raise AlvaoServiceException(
                    error_message, status_code=response.status_code, response=error_data
                )

            # Return empty dict for 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f'Alvao API timeout after {self.timeout}s')
            raise AlvaoServiceException(f'API request timed out after {self.timeout} seconds')

        except requests.exceptions.ConnectionError as e:
            logger.error(f'Alvao API connection error: {e}')
            raise AlvaoServiceException(f'Could not connect to Alvao API: {e}')

        except requests.exceptions.RequestException as e:
            logger.error(f'Alvao API request error: {e}')
            raise AlvaoServiceException(f'API request failed: {e}')

    def create_ticket(self, ticket_data: TicketData) -> TicketResponse:
        """
        Create a new ticket in Alvao Service Desk.

        Args:
            ticket_data: Data for the new ticket

        Returns:
            TicketResponse with the created ticket information
        """
        payload = ticket_data.to_dict()

        # Add default service ID if not specified
        if not payload.get('serviceId') and self.default_service_id:
            payload['serviceId'] = self.default_service_id

        logger.info(f'Creating Alvao ticket for {ticket_data.requester_email}')

        response_data = self._make_request('POST', '/tickets', data=payload)

        result = TicketResponse.from_dict(response_data)
        logger.info(f'Created Alvao ticket: {result.ticket_id}')

        return result

    def get_ticket(self, ticket_id: str) -> TicketInfo:
        """
        Get information about an existing ticket.

        Args:
            ticket_id: The ID of the ticket to retrieve

        Returns:
            TicketInfo with ticket details
        """
        logger.debug(f'Fetching Alvao ticket: {ticket_id}')

        response_data = self._make_request('GET', f'/tickets/{ticket_id}')

        return TicketInfo(
            ticket_id=str(response_data.get('ticketId', response_data.get('id', ticket_id))),
            ticket_number=response_data.get('ticketNumber', response_data.get('number')),
            subject=response_data.get('subject', ''),
            status=response_data.get('status', response_data.get('state', '')),
            requester_email=response_data.get(
                'requesterEmail', response_data.get('requester', {}).get('email', '')
            ),
            created_at=response_data.get('createdAt', response_data.get('created')),
            updated_at=response_data.get('updatedAt', response_data.get('modified')),
            url=response_data.get('url', response_data.get('webUrl')),
            raw_response=response_data,
        )

    def get_tickets_by_requester(self, requester_email: str) -> list[TicketInfo]:
        """
        Get all tickets for a specific requester.

        Args:
            requester_email: Email of the requester

        Returns:
            List of TicketInfo objects
        """
        logger.debug(f'Fetching Alvao tickets for: {requester_email}')

        response_data = self._make_request('GET', '/tickets', params={'requester': requester_email})

        # Handle both array response and paginated response
        tickets_list = response_data
        if isinstance(response_data, dict):
            tickets_list = response_data.get('items', response_data.get('tickets', []))

        return [
            TicketInfo(
                ticket_id=str(t.get('ticketId', t.get('id', ''))),
                ticket_number=t.get('ticketNumber', t.get('number')),
                subject=t.get('subject', ''),
                status=t.get('status', t.get('state', '')),
                requester_email=requester_email,
                created_at=t.get('createdAt', t.get('created')),
                updated_at=t.get('updatedAt', t.get('modified')),
                url=t.get('url', t.get('webUrl')),
                raw_response=t,
            )
            for t in tickets_list
        ]

    def health_check(self) -> bool:
        """
        Check if the Alvao API is available.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try to access a simple endpoint
            self._make_request('GET', '/health', params={})
            return True
        except AlvaoServiceException:
            # Some Alvao instances might not have a health endpoint
            # Try listing tickets with a limit of 1
            try:
                self._make_request('GET', '/tickets', params={'limit': 1})
                return True
            except AlvaoServiceException:
                return False

    def close(self) -> None:
        """Close the session and release resources."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
