"""Ticketing view helpers."""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme

from shared.dtos import UnifiedDataset
from shared.services import UnifiedCatalogService
from ticketing.cart import CartService


@dataclass(frozen=True)
class CartToggleRequest:
    """POST payload for dataset cart toggles rendered from catalogue cards."""

    app: str
    name: str
    title: str
    btn_style: str


def build_cart_page_context(session, form) -> dict:
    return {'cart': CartService.get(session), 'form': form}


def get_cart_toggle_request(request) -> CartToggleRequest:
    """Extract the cart toggle payload from a POST request."""
    return CartToggleRequest(
        app=request.POST.get('app', ''),
        name=request.POST.get('name', ''),
        title=request.POST.get('title', ''),
        btn_style=request.POST.get('btn_style', 'hero'),
    )


def resolve_cart_dataset(
    toggle_request: CartToggleRequest,
    *,
    service: UnifiedCatalogService | None = None,
) -> UnifiedDataset | None:
    """Return the catalogue dataset referenced by a cart toggle request."""
    if not toggle_request.app or not toggle_request.name:
        return None

    catalog_service = service or UnifiedCatalogService()
    dataset, _distributions = catalog_service.get_single_dataset(
        toggle_request.app,
        toggle_request.name,
    )
    return dataset


def build_cart_toggle_response_context(
    session,
    *,
    toggle_request: CartToggleRequest,
) -> dict:
    """Build the shared context for the HTMX cart toggle partial."""
    template_name = (
        'includes/_cart_inline_btn.html'
        if toggle_request.btn_style == 'inline'
        else 'includes/_cart_add_btn.html'
    )
    return {
        'cart_toggle_template': template_name,
        'cart_app': toggle_request.app,
        'cart_source': toggle_request.app,
        'cart_name': toggle_request.name,
        'cart_title': toggle_request.title,
        'cart_item_key': CartService.item_key(toggle_request.app, toggle_request.name),
        'cart_item_keys': CartService.item_keys(session),
        'cart_count': CartService.count(session),
    }


def render_cart_toggle_response(request, toggle_request: CartToggleRequest) -> HttpResponse:
    """Render the HTMX fragment that updates the button and cart badge together."""
    response_html = render_to_string(
        'ticketing/_cart_toggle_response.html',
        build_cart_toggle_response_context(
            request.session,
            toggle_request=toggle_request,
        ),
        request=request,
    )
    return HttpResponse(response_html)


def get_safe_redirect_target(request) -> str:
    """Validate the post-action redirect target for non-HTMX cart requests."""
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return '/'
    return next_url
