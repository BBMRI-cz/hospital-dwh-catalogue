from __future__ import annotations

from django.http import HttpResponse
from django.views.generic import View

from shared.export import build_complete_jsonld, build_complete_turtle, dump_jsonld
from shared.services import UnifiedCatalogService


def _jsonld_response() -> HttpResponse:
    catalogs, orphan_datasets = UnifiedCatalogService().get_complete_export_catalogue()
    return HttpResponse(
        dump_jsonld(build_complete_jsonld(catalogs, orphan_datasets)),
        content_type='application/ld+json; charset=utf-8',
    )


def _turtle_response() -> HttpResponse:
    catalogs, orphan_datasets = UnifiedCatalogService().get_complete_export_catalogue()
    return HttpResponse(
        build_complete_turtle(catalogs, orphan_datasets),
        content_type='text/turtle; charset=utf-8',
    )


class CatalogueJsonLdApiView(View):
    """Public aggregate HealthDCAT-AP export endpoint in JSON-LD."""

    def get(self, request) -> HttpResponse:
        return _jsonld_response()


class CatalogueTurtleApiView(View):
    """Public aggregate HealthDCAT-AP export endpoint in Turtle."""

    def get(self, request) -> HttpResponse:
        return _turtle_response()
