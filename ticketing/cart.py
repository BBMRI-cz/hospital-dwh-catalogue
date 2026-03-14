"""
Cart helper for the ticketing app.

Cart items are stored in the session as a list of dicts:
    session['cart'] = [
        {'source': 'warehouse', 'name': 'my_dataset', 'title': 'My Dataset'},
        ...
    ]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.sessions.backends.base import SessionBase

CART_SESSION_KEY = 'cart'
CART_MAX_ITEMS = 50


class CartService:
    """Session-backed cart for dataset access requests."""

    @staticmethod
    def get(session: 'SessionBase') -> list[dict]:
        """Return the current cart items list (may be empty)."""
        return list(session.get(CART_SESSION_KEY, []))

    @staticmethod
    def add(session: 'SessionBase', source: str, name: str, title: str) -> bool:
        """
        Add a dataset to the cart.

        Idempotent — adding the same (source, name) twice is a no-op.
        Returns True if the item was added, False if it was already present
        or the cart is full.
        """
        cart: list[dict] = list(session.get(CART_SESSION_KEY, []))

        # Already present — idempotent
        for item in cart:
            if item['source'] == source and item['name'] == name:
                return False

        if len(cart) >= CART_MAX_ITEMS:
            return False

        cart.append({'source': source, 'name': name, 'title': title})
        session[CART_SESSION_KEY] = cart
        session.modified = True
        return True

    @staticmethod
    def remove(session: 'SessionBase', source: str, name: str) -> bool:
        """
        Remove a dataset from the cart.

        Returns True if removed, False if it was not in the cart.
        """
        cart: list[dict] = list(session.get(CART_SESSION_KEY, []))
        new_cart = [i for i in cart if not (i['source'] == source and i['name'] == name)]
        if len(new_cart) == len(cart):
            return False
        session[CART_SESSION_KEY] = new_cart
        session.modified = True
        return True

    @staticmethod
    def clear(session: 'SessionBase') -> None:
        """Empty the cart."""
        session[CART_SESSION_KEY] = []
        session.modified = True

    @staticmethod
    def count(session: 'SessionBase') -> int:
        """Return the number of items in the cart."""
        return len(session.get(CART_SESSION_KEY, []))
