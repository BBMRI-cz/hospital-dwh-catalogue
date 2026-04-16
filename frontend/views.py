"""Catalogue frontend views."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import View

from frontend.presentation import (
    build_catalogue_index_context,
    build_dataset_detail_context,
    build_distribution_detail_context,
)
from shared.export import build_jsonld, build_turtle, has_distributions
from shared.services import UnifiedCatalogService


def page_not_found(request, exception):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, '404.html', status=404)


class CatalogueIndexView(LoginRequiredMixin, View):
    """Render the catalogue index and its HTMX results partial."""

    def get(self, request):
        context = build_catalogue_index_context(request)

        if request.headers.get('HX-Request'):
            return render(request, 'catalogue/components/_results.html', context)

        return render(request, 'catalogue/index.html', context)


class DatasetDetailView(LoginRequiredMixin, View):
    """Render the detail page for a single dataset."""

    template_name = 'catalogue/dataset_detail.html'

    def get(self, request, app: str, name: str):
        return render(
            request,
            self.template_name,
            build_dataset_detail_context(request, app=app, name=name),
        )


class DatasetRdfExportView(LoginRequiredMixin, View):
    """Download a Turtle export for a single dataset."""

    def get(self, request, app: str, name: str) -> HttpResponse:
        export_dataset = UnifiedCatalogService().get_export_dataset(app, name)
        if export_dataset is None:
            raise Http404('Dataset not found')

        if not has_distributions(export_dataset):
            raise Http404('Dataset has no distributions')

        response = HttpResponse(
            build_turtle(export_dataset),
            content_type='text/turtle; charset=utf-8',
        )
        response['Content-Disposition'] = f'attachment; filename="{name}.ttl"'
        return response


class DatasetJsonLdDownloadView(LoginRequiredMixin, View):
    """Download a JSON-LD export for a single dataset."""

    def get(self, request, app: str, name: str) -> HttpResponse:
        export_dataset = UnifiedCatalogService().get_export_dataset(app, name)
        if export_dataset is None:
            raise Http404('Dataset not found')

        if not has_distributions(export_dataset):
            raise Http404('Dataset has no distributions')

        response = HttpResponse(
            build_jsonld(export_dataset),
            content_type='application/ld+json; charset=utf-8',
        )
        response['Content-Disposition'] = f'attachment; filename="{name}.jsonld"'
        return response


class DistributionDetailView(LoginRequiredMixin, View):
    """Render the detail page for a single distribution."""

    template_name = 'catalogue/distribution_detail.html'

    def get(self, request, app: str, name: str):
        return render(
            request,
            self.template_name,
            build_distribution_detail_context(request, app=app, name=name),
        )
