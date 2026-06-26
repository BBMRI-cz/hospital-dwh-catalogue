"""Email helpers for HealthDCAT contact-point import/export."""

from __future__ import annotations

MAILTO_PREFIX = 'mailto:'


def normalise_email(value: str | None) -> str | None:
    """Return a plain email address, accepting either plain or mailto input."""
    if value is None:
        return None

    email = value.strip()
    while email.lower().startswith(MAILTO_PREFIX):
        email = email[len(MAILTO_PREFIX) :].strip()
    return email or None


def mailto_iri(value: str | None) -> str | None:
    """Return a single mailto IRI for a plain or already-prefixed email."""
    email = normalise_email(value)
    if email is None:
        return None
    return f'{MAILTO_PREFIX}{email}'
