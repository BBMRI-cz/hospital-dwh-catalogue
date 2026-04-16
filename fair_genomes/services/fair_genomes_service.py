"""Service facade for the FAIR Genomes catalogue sync."""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.db import transaction

from fair_genomes.services.client import detect_rdf_format, fetch_rdf
from fair_genomes.services.persistence import empty_rdf_report, process_graph
from fair_genomes.services.stats import (
    introspect_molgenis_schema,
    sync_stats,
)
from fair_genomes.services.stats import (
    sync_single_stat as sync_single_stat_helper,
)

logger = logging.getLogger(__name__)


class FairGenomesAPIException(Exception):
    """Raised when the FDP endpoint cannot be reached or its data cannot be parsed."""


class FairGenomesService:
    """Sync FAIR Genomes catalogue data from RDF and GraphQL sources."""

    def __init__(
        self,
        rdf_url: str | None = None,
        api_url: str | None = None,
        api_token: str | None = None,
        timeout: tuple[int, int] | int = (10, 60),
    ):
        def _cfg(value: str | None, key: str) -> str:
            return value if value is not None else getattr(settings, key, '')

        self.rdf_url = _cfg(rdf_url, 'FAIR_GENOMES_RDF_URL')
        self.graphql_url = _cfg(api_url, 'FAIR_GENOMES_API_URL')
        self.api_token = _cfg(api_token, 'FAIR_GENOMES_API_TOKEN')
        self.timeout = timeout

    def sync(self) -> dict:
        if not self.rdf_url and not self.graphql_url:
            return {
                'status': 'skipped',
                'reason': (
                    'Neither FAIR_GENOMES_RDF_URL nor FAIR_GENOMES_API_URL is configured '
                    '— set at least one in the environment'
                ),
            }

        started_at = time.monotonic()
        logger.info(
            'Sync started',
            extra={'rdf_url': self.rdf_url, 'graphql_url': self.graphql_url},
        )

        graph = None
        if self.rdf_url:
            try:
                response = fetch_rdf(self.rdf_url, self.timeout)
                rdf_format = detect_rdf_format(response)
                from rdflib import Graph

                graph = Graph()
                graph.parse(data=response.text, format=rdf_format)
            except Exception as exc:  # - preserve existing API surface
                raise FairGenomesAPIException(
                    f'Failed to parse RDF from {self.rdf_url}: {exc}'
                ) from exc
            logger.info('RDF fetched and parsed', extra={'triples': len(graph)})

        with transaction.atomic(using='fair_genomes_db'):
            report = process_graph(graph, rdf_url=self.rdf_url) if graph else empty_rdf_report()

        report['graphql_url'] = self.graphql_url or ''
        report['stats'] = (
            sync_stats(
                graphql_url=self.graphql_url,
                api_token=self.api_token,
                timeout=self.timeout,
            )
            if self.graphql_url
            else None
        )
        report['duration_seconds'] = round(time.monotonic() - started_at, 2)

        logger.info(
            'Sync completed',
            extra={
                'status': report['status'],
                'duration_seconds': report['duration_seconds'],
            },
        )
        return report

    def _process_graph(self, graph) -> dict:
        """Retain the extracted graph-persistence entrypoint for tests and tooling."""
        return process_graph(graph, rdf_url=self.rdf_url)

    def _sync_stats(self) -> dict:
        """Retain the extracted stats-sync entrypoint for tests and tooling."""
        return sync_stats(
            graphql_url=self.graphql_url,
            api_token=self.api_token,
            timeout=self.timeout,
        )

    def sync_single_stat(self, table: str, column: str) -> tuple[bool, str]:
        return sync_single_stat_helper(
            graphql_url=self.graphql_url,
            api_token=self.api_token,
            timeout=self.timeout,
            table=table,
            column=column,
        )

    def introspect_molgenis_schema(self) -> dict[str, list[str]]:
        return introspect_molgenis_schema(
            graphql_url=self.graphql_url,
            api_token=self.api_token,
            timeout=self.timeout,
        )

    def close(self) -> None:
        """Retained for interface compatibility."""

    def __enter__(self) -> FairGenomesService:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
