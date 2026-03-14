"""
Context processors for the ticketing app.

Provides cart_count to every template so the header badge is always current.
"""

from __future__ import annotations

from ticketing.cart import CartService


def cart_count(request) -> dict:
    """Inject cart item count into every template context."""
    return {'cart_count': CartService.count(request.session)}
