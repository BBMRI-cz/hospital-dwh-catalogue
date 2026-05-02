"""Operational sync-state helpers for FAIR Genomes integrations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.utils import timezone

DB = 'fair_genomes_db'


def _sync_state_model():
    from fair_genomes.models import FairGenomesSyncState

    return FairGenomesSyncState


def _now():
    return timezone.now()


def mark_started(source_type: str, *, source_url: str = '') -> None:
    """Record that a source check/synchronisation has started."""
    model = _sync_state_model()
    model.objects.using(DB).update_or_create(
        source_type=source_type,
        defaults={
            'source_url': source_url or '',
            'status': model.Status.RUNNING,
            'last_checked_at': _now(),
            'duration_seconds': None,
            'summary': {},
            'error_message': '',
        },
    )


def mark_success(
    source_type: str,
    *,
    source_url: str = '',
    duration_seconds: float | None = None,
    summary: Mapping[str, Any] | None = None,
) -> None:
    """Record a successful source synchronisation."""
    model = _sync_state_model()
    now = _now()
    model.objects.using(DB).update_or_create(
        source_type=source_type,
        defaults={
            'source_url': source_url or '',
            'status': model.Status.SUCCESS,
            'last_checked_at': now,
            'last_success_at': now,
            'duration_seconds': duration_seconds,
            'summary': dict(summary or {}),
            'error_message': '',
        },
    )


def mark_failed(
    source_type: str,
    *,
    source_url: str = '',
    duration_seconds: float | None = None,
    summary: Mapping[str, Any] | None = None,
    error_message: str = '',
) -> None:
    """Record a failed source synchronisation."""
    model = _sync_state_model()
    now = _now()
    model.objects.using(DB).update_or_create(
        source_type=source_type,
        defaults={
            'source_url': source_url or '',
            'status': model.Status.FAILED,
            'last_checked_at': now,
            'last_failure_at': now,
            'duration_seconds': duration_seconds,
            'summary': dict(summary or {}),
            'error_message': error_message,
        },
    )


def mark_skipped(
    source_type: str,
    *,
    source_url: str = '',
    summary: Mapping[str, Any] | None = None,
    reason: str = '',
) -> None:
    """Record that a source synchronisation was skipped."""
    model = _sync_state_model()
    model.objects.using(DB).update_or_create(
        source_type=source_type,
        defaults={
            'source_url': source_url or '',
            'status': model.Status.SKIPPED,
            'last_checked_at': _now(),
            'duration_seconds': None,
            'summary': dict(summary or {}),
            'error_message': reason,
        },
    )


def get_state_map() -> dict[str, object]:
    model = _sync_state_model()
    return {state.source_type: state for state in model.objects.using(DB).all()}


def rdf_report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    saved = report.get('saved', {})
    fetched = report.get('fetched', {})
    deleted = report.get('deleted', {})
    skipped = report.get('skipped', {})
    entity_types = ('contact_points', 'agents', 'catalogs', 'datasets', 'distributions')

    return {
        'status': report.get('status', ''),
        'fetched': {entity: len(fetched.get(entity, [])) for entity in entity_types},
        'created': {
            entity: len(saved.get(entity, {}).get('created', [])) for entity in entity_types
        },
        'updated': {
            entity: len(saved.get(entity, {}).get('updated', [])) for entity in entity_types
        },
        'deleted': dict(deleted),
        'skipped': {entity: len(items) for entity, items in skipped.items()},
    }


def stats_report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'updated': int(report.get('updated', 0) or 0),
        'failed': int(report.get('failed', 0) or 0),
        'errors': list(report.get('errors', []) or [])[:10],
    }
