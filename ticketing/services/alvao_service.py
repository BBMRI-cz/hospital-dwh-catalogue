"""
Alvao Service Desk REST API integration.

This service handles communication with the real Alvao Service Desk API (v1.3).
Uses a service account with basic authentication to create tickets on behalf of users.

Alvao API spec: https://app.swaggerhub.com/apis-docs/A3555/ALVAO_REST_API/v1.3
Base URL pattern: https://{server}/AlvaoRestApi/v1/
"""

import contextlib
import logging
import time

import requests

from django.conf import settings

from .base import TicketData, TicketResponse

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AlvaoServiceException(Exception):
    """Custom exception for Alvao API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict | None = None,
        *,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.retryable = retryable


class AlvaoService:
    """
    Service class for interacting with Alvao Service Desk REST API v1.3.

    Uses a dedicated Alvao service account (basic auth) to create tickets.
    The service account must have permissions to create tickets in the
    configured service.

    Required settings:
        ALVAO_API_URL: Base URL, e.g. https://alvao.company.com/AlvaoRestApi/v1
        ALVAO_SERVICE_ACCOUNT_USERNAME: Service account login name
        ALVAO_SERVICE_ACCOUNT_PASSWORD: Service account password
        ALVAO_DEFAULT_SERVICE_ID: Service ID for new tickets (required by Alvao)

    Usage:
        service = AlvaoService()
        response = service.create_ticket(ticket_data)
    """

    def __init__(
        self,
        api_url: str | None = None,
        service_account_username: str | None = None,
        service_account_password: str | None = None,
        default_service_id: int | None = None,
        timeout: int = 30,
    ):
        self.api_url = (api_url or getattr(settings, 'ALVAO_API_URL', '')).rstrip('/')
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
        """Lazy-load and reuse requests session with service account auth."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
            )
            if self.service_account_username:
                self._session.auth = (
                    self.service_account_username,
                    self.service_account_password,
                )
        return self._session

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """
        Make an HTTP request to the Alvao API with automatic retry on transient failures.

        Retries up to _MAX_RETRIES times with exponential backoff for 429/5xx errors
        and connection/timeout errors.
        """
        url = f'{self.api_url}/{endpoint.lstrip("/")}'
        last_exception: AlvaoServiceException | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                return self._do_request(method, url, data, params)
            except AlvaoServiceException as exc:
                last_exception = exc
                if not exc.retryable or attempt == _MAX_RETRIES - 1:
                    raise
                wait = _RETRY_BACKOFF_BASE**attempt
                logger.warning(
                    'Alvao API transient error (attempt %d/%d), retrying in %ds: %s',
                    attempt + 1,
                    _MAX_RETRIES,
                    wait,
                    exc,
                )
                time.sleep(wait)

        # Should not reach here, but satisfy type checker
        raise last_exception  # type: ignore[misc]

    def _do_request(
        self,
        method: str,
        url: str,
        data: dict | None,
        params: dict | None,
    ) -> dict:
        """Execute a single HTTP request."""
        try:
            logger.debug('Alvao API %s %s', method, url)

            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout,
            )

            logger.debug('Alvao API response: %s', response.status_code)

            if response.status_code >= 400:
                error_data = None
                with contextlib.suppress(Exception):
                    error_data = response.json()

                error_message = f'Alvao API error: {response.status_code}'
                if error_data and isinstance(error_data, dict):
                    error_message = error_data.get('message', error_message)

                logger.error('Alvao API error: %s - %s', response.status_code, error_message)
                raise AlvaoServiceException(
                    error_message,
                    status_code=response.status_code,
                    response=error_data,
                    retryable=response.status_code in _RETRYABLE_STATUS_CODES,
                )

            if response.status_code == 204:
                return {}

            return response.json()

        except requests.exceptions.Timeout:
            logger.error('Alvao API timeout after %ds', self.timeout)
            raise AlvaoServiceException(
                f'API request timed out after {self.timeout} seconds',
                retryable=True,
            )

        except requests.exceptions.ConnectionError as e:
            logger.error('Alvao API connection error: %s', e)
            raise AlvaoServiceException(
                f'Could not connect to Alvao API: {e}',
                retryable=True,
            )

        except requests.exceptions.RequestException as e:
            logger.error('Alvao API request error: %s', e)
            raise AlvaoServiceException(f'API request failed: {e}')

    def create_ticket(self, ticket_data: TicketData) -> TicketResponse:
        """
        Create a new ticket in Alvao Service Desk.

        POST /tickets - requires `requester` and `serviceId` in the payload.
        Returns 201 Created with the ticket object.
        """
        payload = ticket_data.to_dict()

        # serviceId is required by Alvao; inject default if not already set
        if not payload.get('serviceId') and self.default_service_id:
            payload['serviceId'] = self.default_service_id

        logger.info(
            'Creating Alvao ticket for %s (service=%s)',
            ticket_data.requester_email,
            payload.get('serviceId'),
        )

        response_data = self._make_request('POST', '/tickets', data=payload)

        result = TicketResponse.from_dict(response_data)
        logger.info('Created Alvao ticket: id=%s tag=%s', result.ticket_id, result.ticket_number)

        return result

    def close(self) -> None:
        """Close the session and release resources."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
