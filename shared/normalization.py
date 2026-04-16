"""Shared normalization helpers used across services and presentation mappers."""

from __future__ import annotations


def _split_unique_values(value_str: str | None, separator: str) -> list[str]:
    values = [value.strip() for value in (value_str or '').split(separator) if value.strip()]
    return list(dict.fromkeys(values))


def parse_keywords(keyword_str: str | None) -> list[str]:
    """Parse a comma-separated keyword string into a clean list."""
    return _split_unique_values(keyword_str, ',')


def parse_multi_values(value_str: str | None) -> list[str]:
    """Parse a semicolon-separated multi-value string into a clean list."""
    return _split_unique_values(value_str, ';')


def derive_status(access_rights: str | None) -> str:
    """Derive the catalogue status from an access-rights URI or label."""
    if not access_rights:
        return 'raw'

    access_rights_upper = access_rights.upper()
    if 'PUBLIC' in access_rights_upper and 'NON' not in access_rights_upper:
        return 'ready'
    if 'NON_PUBLIC' in access_rights_upper or 'NONPUBLIC' in access_rights_upper:
        return 'unavailable'
    if 'CLOSED' in access_rights_upper:
        return 'unavailable'
    return 'raw'
