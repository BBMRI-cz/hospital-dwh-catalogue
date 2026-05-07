"""Service facade for the FAIR Genomes catalogue sync."""

from __future__ import annotations

import logging
import time

from rdflib import Graph

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
from fair_genomes.services.sync_state import (
    mark_failed,
    mark_skipped,
    mark_started,
    mark_success,
    rdf_report_summary,
    stats_report_summary,
)

logger = logging.getLogger(__name__)

RDF_METADATA_SOURCE = 'rdf_metadata'
STATISTICS_SOURCE = 'statistics'


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
            mark_skipped(
                RDF_METADATA_SOURCE,
                reason='FAIR_GENOMES_RDF_URL is not configured',
            )
            mark_skipped(
                STATISTICS_SOURCE,
                reason='FAIR_GENOMES_API_URL is not configured',
            )
            return {
                'status': 'skipped',
                'reason': (
                    'Neither FAIR_GENOMES_RDF_URL nor FAIR_GENOMES_API_URL is configured '
                    '- set at least one in the environment'
                ),
            }

        started_at = time.monotonic()
        logger.info(
            'Sync started',
            extra={'rdf_url': self.rdf_url, 'graphql_url': self.graphql_url},
        )

        graph = None
        report = empty_rdf_report()
        if self.rdf_url:
            rdf_started_at = time.monotonic()
            mark_started(RDF_METADATA_SOURCE, source_url=self.rdf_url)
            try:
                response = fetch_rdf(self.rdf_url, self.timeout)
                rdf_format = detect_rdf_format(response)

                graph = Graph()
                graph.parse(data=response.text, format=rdf_format)

                with transaction.atomic(using='fair_genomes_db'):
                    report = process_graph(graph, rdf_url=self.rdf_url)
            except Exception as exc:
                message = f'Failed to parse RDF from {self.rdf_url}: {exc}'
                mark_failed(
                    RDF_METADATA_SOURCE,
                    source_url=self.rdf_url,
                    duration_seconds=round(time.monotonic() - rdf_started_at, 2),
                    error_message=message,
                )
                report['status'] = 'failed'
                report['rdf_url'] = self.rdf_url
                report['error'] = message
                logger.exception('RDF metadata sync failed')
            else:
                logger.info('RDF fetched and parsed', extra={'triples': len(graph)})
                mark_success(
                    RDF_METADATA_SOURCE,
                    source_url=self.rdf_url,
                    duration_seconds=round(time.monotonic() - rdf_started_at, 2),
                    summary=rdf_report_summary(report),
                )
        else:
            mark_skipped(
                RDF_METADATA_SOURCE,
                reason='FAIR_GENOMES_RDF_URL is not configured',
            )

        report['graphql_url'] = self.graphql_url or ''
        if self.graphql_url:
            stats_started_at = time.monotonic()
            mark_started(STATISTICS_SOURCE, source_url=self.graphql_url)
            try:
                stats = sync_stats(
                    graphql_url=self.graphql_url,
                    api_token=self.api_token,
                    timeout=self.timeout,
                )
            except Exception as exc:
                message = f'Failed to synchronise statistics from {self.graphql_url}: {exc}'
                stats = {
                    'updated': 0,
                    'failed': 1,
                    'errors': [message],
                }
                stats_summary = stats_report_summary(stats)
                mark_failed(
                    STATISTICS_SOURCE,
                    source_url=self.graphql_url,
                    duration_seconds=round(time.monotonic() - stats_started_at, 2),
                    summary=stats_summary,
                    error_message=message,
                )
                logger.exception('FAIR Genomes statistics sync failed')
            else:
                stats_summary = stats_report_summary(stats)
                if stats.get('failed'):
                    mark_failed(
                        STATISTICS_SOURCE,
                        source_url=self.graphql_url,
                        duration_seconds=round(time.monotonic() - stats_started_at, 2),
                        summary=stats_summary,
                        error_message='; '.join(stats_summary['errors']),
                    )
                else:
                    mark_success(
                        STATISTICS_SOURCE,
                        source_url=self.graphql_url,
                        duration_seconds=round(time.monotonic() - stats_started_at, 2),
                        summary=stats_summary,
                    )
            report['stats'] = stats
        else:
            report['stats'] = None
            mark_skipped(
                STATISTICS_SOURCE,
                reason='FAIR_GENOMES_API_URL is not configured',
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
