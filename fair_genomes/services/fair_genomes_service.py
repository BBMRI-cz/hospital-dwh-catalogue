"""
Service layer for Fair Genomes GraphQL API integration.
Handles API communication, data transformation, and persistence.
"""

import logging
from datetime import datetime
from typing import Any

import requests

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from fair_genomes.models import Personal

logger = logging.getLogger(__name__)


class FairGenomesAPIException(Exception):
    """Custom exception for Fair Genomes API errors."""

    pass


class FairGenomesService:
    """
    Service class for interacting with Fair Genomes GraphQL API.

    This class encapsulates all API communication logic and provides
    a clean interface for fetching and syncing data.
    """

    def __init__(self, api_url: str | None = None, api_token: str | None = None, timeout: int = 30):
        """
        Initialize the service with API credentials.

        Args:
            api_url: GraphQL API endpoint URL
            api_token: Authentication token
            timeout: Request timeout in seconds
        """
        self.api_url = api_url or settings.FAIR_GENOMES_API_URL
        self.api_token = api_token or settings.FAIR_GENOMES_API_TOKEN
        self.timeout = timeout
        self._session = None

    @property
    def session(self) -> requests.Session:
        """Lazy-load and reuse requests session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {'Content-Type': 'application/json', 'x-molgenis-token': self.api_token}
            )
        return self._session

    def _execute_query(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Query response data

        Raises:
            FairGenomesAPIException: On API or network errors
        """
        payload: dict[str, Any] = {'query': query}
        if variables:
            payload['variables'] = variables

        try:
            logger.debug(f'Executing GraphQL query to {self.api_url}')
            response = self.session.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if 'errors' in data:
                error_messages = [e.get('message', 'Unknown error') for e in data['errors']]
                raise FairGenomesAPIException(f'GraphQL errors: {", ".join(error_messages)}')

            return data.get('data', {})

        except requests.exceptions.Timeout:
            logger.error(f'Request timeout after {self.timeout}s')
            raise FairGenomesAPIException(f'API request timed out after {self.timeout} seconds')

        except requests.exceptions.RequestException as e:
            logger.error(f'API request failed: {e}')
            raise FairGenomesAPIException(f'Failed to connect to API: {e!s}')

        except ValueError as e:
            logger.error(f'Invalid JSON response: {e}')
            raise FairGenomesAPIException('API returned invalid JSON response')

    def fetch_personal_data(self) -> list[dict[str, Any]]:
        """
        Fetch all Personal records from the API.

        Returns:
            List of personal data records

        Raises:
            FairGenomesAPIException: On API errors
        """
        query = """
        query {
            Personal {
                personalIdentifier
                yearofbirth
                mg_insertedBy
                mg_insertedOn
                mg_updatedBy
                mg_updatedOn
            }
        }
        """

        logger.info('Fetching Personal data from Fair Genomes API')
        data = self._execute_query(query)
        personal_records = data.get('Personal', [])

        logger.info(f'Successfully fetched {len(personal_records)} Personal records')
        return personal_records

    def introspect_schema(self) -> dict[str, Any]:
        """
        Introspect the GraphQL schema to discover available types.

        Returns:
            Schema introspection data
        """
        query = """
        query IntrospectionQuery {
            __schema {
                queryType { name }
                types {
                    kind
                    name
                    description
                    fields {
                        name
                        type {
                            name
                            kind
                            ofType { name kind }
                        }
                    }
                }
            }
        }
        """

        logger.info('Introspecting GraphQL schema')
        return self._execute_query(query)

    @staticmethod
    def _parse_datetime(dt_string: str | None) -> datetime | None:
        """
        Parse ISO datetime string from API.

        Args:
            dt_string: ISO format datetime string

        Returns:
            Parsed datetime object or None
        """
        if not dt_string:
            return None

        try:
            # Handle both with and without timezone
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            # Ensure timezone aware
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime '{dt_string}': {e}")
            return None

    def sync_personal_data(self, dry_run: bool = False) -> dict[str, int]:
        """
        Sync Personal data from API to local database.

        Args:
            dry_run: If True, fetch but don't save data

        Returns:
            Dictionary with sync statistics (created, updated, failed)

        Raises:
            FairGenomesAPIException: On API errors
        """
        stats = {'created': 0, 'updated': 0, 'failed': 0, 'total': 0}

        # Fetch data from API
        try:
            records = self.fetch_personal_data()
            stats['total'] = len(records)
        except FairGenomesAPIException:
            logger.exception('Failed to fetch Personal data')
            raise

        if dry_run:
            logger.info(f'DRY RUN: Would process {len(records)} records')
            return stats

        # Sync to database
        with transaction.atomic(using='fair_genomes_db'):
            for record in records:
                try:
                    personal_id = record.get('personalIdentifier')

                    _personal, created = Personal.objects.using('fair_genomes_db').update_or_create(
                        personal_identifier=personal_id,
                        defaults={
                            'year_of_birth': record.get('yearofbirth'),
                            'inserted_by': record.get('mg_insertedBy'),
                            'inserted_on': self._parse_datetime(record.get('mg_insertedOn')),
                            'updated_by': record.get('mg_updatedBy'),
                            'updated_on': self._parse_datetime(record.get('mg_updatedOn')),
                        },
                    )

                    if created:
                        stats['created'] += 1
                        logger.debug(f'Created Personal record: {personal_id}')
                    else:
                        stats['updated'] += 1
                        logger.debug(f'Updated Personal record: {personal_id}')

                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f'Failed to sync record {record.get("personalIdentifier")}: {e}')

        logger.info(
            f'Sync completed: {stats["created"]} created, '
            f'{stats["updated"]} updated, {stats["failed"]} failed'
        )

        return stats

    def close(self):
        """Close the requests session."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
