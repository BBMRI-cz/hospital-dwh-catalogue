"""Context processors for ticketing templates."""

from __future__ import annotations

from ticketing.cart import CartService


def cart_count(request) -> dict:
    return {'cart_count': CartService.count(request.session)}
