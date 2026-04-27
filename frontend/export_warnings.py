"""Helpers for surfacing non-fatal metadata export warnings."""

from __future__ import annotations

import json

from django.http import HttpResponse

from shared.export_types import ExportWarning


def export_warning_messages(warnings: tuple[ExportWarning, ...]) -> list[str]:
    """Return user-facing warning messages."""
    return [warning.message for warning in warnings]


def add_export_warning_headers(
    response: HttpResponse,
    warnings: tuple[ExportWarning, ...],
) -> HttpResponse:
    """Attach export warning metadata to a response without changing the body."""
    messages = export_warning_messages(warnings)
    response['X-Metadata-Export-Warning-Count'] = str(len(messages))
    if messages:
        response['X-Metadata-Export-Warnings'] = json.dumps(messages, ensure_ascii=False)
    return response
