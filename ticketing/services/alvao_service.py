"""
Alvao Service Desk REST API integration.

This service handles communication with the real Alvao Service Desk API (v1.3).
Uses a service account with basic authentication to create tickets on behalf of users.

Alvao API spec: https://app.swaggerhub.com/apis-docs/A3555/ALVAO_REST_API/v1.3
Base URL pattern: https://{server}/AlvaoRestApi/v1/
"""

import contextlib
import json
import logging
import time
from typing import Any

import requests

from django.conf import settings

from .base import TicketData, TicketResponse

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_ERROR_BODY_CHARS = 4000
_USER_MATCH_FIELDS = ('email', 'email2', 'username', 'login', 'name', 'displayname')


def _format_error_detail(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '; '.join(_format_error_detail(item) for item in value)
    if isinstance(value, dict):
        return '; '.join(f'{key}: {_format_error_detail(item)}' for key, item in value.items())
    return str(value)


def _extract_error_message(error_data: Any, fallback: str) -> str:
    if not isinstance(error_data, dict):
        return fallback

    for key in ('message', 'title', 'detail', 'error'):
        value = error_data.get(key)
        if value:
            return _format_error_detail(value)

    errors = error_data.get('errors')
    if errors:
        return _format_error_detail(errors)

    return fallback


def _response_body_for_log(response: requests.Response) -> str:
    with contextlib.suppress(Exception):
        return json.dumps(response.json(), ensure_ascii=False, sort_keys=True)[
            :_MAX_ERROR_BODY_CHARS
        ]

    body = response.text.strip()
    if not body:
        return '<empty>'
    return body[:_MAX_ERROR_BODY_CHARS]


def _ticket_requester_mode(payload: dict | None) -> tuple[str, str]:
    requester = payload.get('requester') if isinstance(payload, dict) else None
    if isinstance(requester, dict):
        return 'explicit', str(
            requester.get('id') or requester.get('email') or requester.get('name') or '<unknown>'
        )
    return 'service_account', '<omitted>'


def _normalized(value: Any) -> str:
    return str(value or '').strip().casefold()


def _extract_users(response_data: Any) -> list[dict[str, Any]]:
    if isinstance(response_data, list):
        return [item for item in response_data if isinstance(item, dict)]
    if isinstance(response_data, dict):
        value = response_data.get('value')
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if 'id' in response_data:
            return [response_data]
    return []


def _user_fields(user: dict[str, Any]) -> dict[str, Any]:
    return {str(key).casefold(): value for key, value in user.items()}


def _extract_user_id(user: dict[str, Any]) -> int | None:
    value = _user_fields(user).get('id')
    with contextlib.suppress(TypeError, ValueError):
        if value not in (None, ''):
            return int(value)
    return None


def _user_matches(user: dict[str, Any], lookup: str) -> bool:
    expected = _normalized(lookup)
    fields = _user_fields(user)
    return any(_normalized(fields.get(key)) == expected for key in _USER_MATCH_FIELDS)


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
                error_message = _extract_error_message(error_data, error_message)
                error_body = _response_body_for_log(response)

                logger.error(
                    'Alvao API error: %s - %s; response_body=%s',
                    response.status_code,
                    error_message,
                    error_body,
                )
                if 'has no SLA' in error_message:
                    requester_mode, requester = _ticket_requester_mode(data)
                    service_id = data.get('serviceId') if isinstance(data, dict) else None
                    logger.error(
                        'Alvao SLA rejection details: requester_mode=%s requester=%s service_id=%s',
                        requester_mode,
                        requester,
                        service_id,
                    )
                raise AlvaoServiceException(
                    error_message,
                    status_code=response.status_code,
                    response=error_data if isinstance(error_data, dict) else None,
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

    def _search_users(self, lookup: str) -> list[dict[str, Any]]:
        users: list[dict[str, Any]] = []
        seen_user_ids: set[int] = set()
        for params in ({'$search': lookup, '$top': 20}, {'search': lookup, 'top': 20}):
            try:
                response_data = self._make_request('GET', '/users', params=params)
            except AlvaoServiceException as exc:
                if exc.status_code == 400:
                    continue
                raise

            for user in _extract_users(response_data):
                user_id = _extract_user_id(user)
                if user_id is None or user_id in seen_user_ids:
                    continue
                seen_user_ids.add(user_id)
                users.append(user)
            if any(_user_matches(user, lookup) for user in users):
                return users
        return users

    def _find_user_id(self, lookup: str) -> int | None:
        lookup = lookup.strip()
        if not lookup:
            return None

        users = self._search_users(lookup)
        matches = [user for user in users if _user_matches(user, lookup)]
        candidates = matches or users

        if len(candidates) == 1:
            return _extract_user_id(candidates[0])
        return None

    def _resolve_requester_id(self, ticket_data: TicketData) -> int:
        lookups: list[str] = []
        for value in (
            ticket_data.requester_email,
            ticket_data.requester_username,
            ticket_data.requester_name,
        ):
            value = str(value or '').strip()
            if value and value not in lookups:
                lookups.append(value)

        if not lookups and self.service_account_username:
            lookups.append(self.service_account_username)

        for lookup in lookups:
            user_id = self._find_user_id(lookup)
            if user_id:
                return user_id

        raise AlvaoServiceException(
            'Could not resolve Alvao requester ID for ticket creation. '
            'Check that the requester exists in Alvao and is searchable by email or username.'
        )

    def create_ticket(self, ticket_data: TicketData) -> TicketResponse:
        """
        Create a new ticket in Alvao Service Desk.

        POST /tickets - requires `serviceId` in the payload. The requester is
        resolved to an Alvao user ID before ticket creation.
        Returns 201 Created with the ticket object.
        """
        payload = ticket_data.to_dict()
        payload['requester'] = {'id': self._resolve_requester_id(ticket_data)}

        # serviceId is required by Alvao; inject default if not already set
        if not payload.get('serviceId') and self.default_service_id:
            payload['serviceId'] = self.default_service_id

        requester_mode, requester = _ticket_requester_mode(payload)
        logger.info(
            'Creating Alvao ticket (requester_mode=%s requester=%s service=%s)',
            requester_mode,
            requester,
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
