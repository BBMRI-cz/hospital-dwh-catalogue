from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.generic import View

from shared.export import build_complete_jsonld, build_complete_turtle, dump_jsonld
from shared.services import UnifiedCatalogService


def _require_auth(request: HttpRequest) -> HttpResponse | None:
    """Return a 401 response if the user is not authenticated, otherwise None."""
    if not request.user.is_authenticated:
        return HttpResponse(status=401)
    return None


def _jsonld_response() -> HttpResponse:
    catalogs, orphan_datasets = UnifiedCatalogService().get_complete_export_catalogue()
    return HttpResponse(
        dump_jsonld(
            build_complete_jsonld(catalogs, orphan_datasets, include_distributions=False)
        ),
        content_type='application/ld+json; charset=utf-8',
    )


def _turtle_response() -> HttpResponse:
    catalogs, orphan_datasets = UnifiedCatalogService().get_complete_export_catalogue()
    return HttpResponse(
        build_complete_turtle(catalogs, orphan_datasets, include_distributions=False),
        content_type='text/turtle; charset=utf-8',
    )


class CatalogueJsonLdApiView(View):
    """Authenticated aggregate HealthDCAT-AP export endpoint in JSON-LD (no distributions)."""

    def get(self, request: HttpRequest) -> HttpResponse:
        denied = _require_auth(request)
        if denied is not None:
            return denied
        return _jsonld_response()


class CatalogueTurtleApiView(View):
    """Authenticated aggregate HealthDCAT-AP export endpoint in Turtle (no distributions)."""

    def get(self, request: HttpRequest) -> HttpResponse:
        denied = _require_auth(request)
        if denied is not None:
            return denied
        return _turtle_response()
