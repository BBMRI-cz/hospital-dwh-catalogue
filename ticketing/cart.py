"""Session-backed cart helpers for ticketing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.sessions.backends.base import SessionBase

logger = logging.getLogger(__name__)

CART_SESSION_KEY = 'cart'
CART_MAX_ITEMS = 50


class CartService:
    """Session-backed cart for dataset access requests."""

    @staticmethod
    def item_key(app: str, name: str) -> str:
        """Return the stable cart identity for a dataset."""
        return f'{app}/{name}'

    @staticmethod
    def get(session: SessionBase) -> list[dict]:
        """Return the current cart items list (may be empty)."""
        return list(session.get(CART_SESSION_KEY, []))

    @staticmethod
    def add(session: SessionBase, app: str, name: str, title: str) -> bool:
        """
        Add a dataset to the cart.

        Adding the same ``(app, name)`` twice is a no-op.
        Returns True if the item was added, False if it was already present
        or the cart is full.
        """
        cart: list[dict] = list(session.get(CART_SESSION_KEY, []))

        for item in cart:
            if item.get('app') == app and item.get('name') == name:
                logger.debug('Cart add no-op: app=%s name=%s already present', app, name)
                return False

        if len(cart) >= CART_MAX_ITEMS:
            logger.debug(
                'Cart add rejected: app=%s name=%s cart full (%d)', app, name, CART_MAX_ITEMS
            )
            return False

        cart.append({'app': app, 'name': name, 'title': title})
        session[CART_SESSION_KEY] = cart
        session.modified = True
        logger.info(
            'Cart add: app=%s name=%s session=%s size=%d',
            app,
            name,
            session.session_key,
            len(cart),
        )
        return True

    @staticmethod
    def contains(session: SessionBase, app: str, name: str) -> bool:
        """Return whether the cart already contains the dataset."""
        return any(
            item.get('app') == app and item.get('name') == name
            for item in session.get(CART_SESSION_KEY, [])
        )

    @staticmethod
    def toggle(session: SessionBase, app: str, name: str, title: str) -> bool:
        """Add the dataset when missing, otherwise remove it."""
        if CartService.contains(session, app, name):
            CartService.remove(session, app, name)
            return False
        return CartService.add(session, app, name, title)

    @staticmethod
    def dataset_ids(session: SessionBase) -> set[str]:
        """Return legacy name-only dataset identifiers currently present in the cart."""
        return {item['name'] for item in session.get(CART_SESSION_KEY, []) if item.get('name')}

    @staticmethod
    def item_keys(session: SessionBase) -> set[str]:
        """Return app/name identities currently present in the cart."""
        return {
            CartService.item_key(item['app'], item['name'])
            for item in session.get(CART_SESSION_KEY, [])
            if item.get('app') and item.get('name')
        }

    @staticmethod
    def remove(session: SessionBase, app: str, name: str) -> bool:
        """
        Remove a dataset from the cart.

        Returns True if removed, False if it was not in the cart.
        """
        cart: list[dict] = list(session.get(CART_SESSION_KEY, []))
        new_cart = [i for i in cart if not (i.get('app') == app and i.get('name') == name)]
        if len(new_cart) == len(cart):
            logger.debug('Cart remove no-op: app=%s name=%s not in cart', app, name)
            return False
        session[CART_SESSION_KEY] = new_cart
        session.modified = True
        logger.info(
            'Cart remove: app=%s name=%s session=%s size=%d',
            app,
            name,
            session.session_key,
            len(new_cart),
        )
        return True

    @staticmethod
    def clear(session: SessionBase) -> None:
        """Empty the cart."""
        logger.info('Cart clear: session=%s', session.session_key)
        session[CART_SESSION_KEY] = []
        session.modified = True

    @staticmethod
    def count(session: SessionBase) -> int:
        """Return the number of items in the cart."""
        return len(session.get(CART_SESSION_KEY, []))
