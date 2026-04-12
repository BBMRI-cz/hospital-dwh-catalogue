"""Class-based views for the catalogue frontend application."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import View

from frontend.catalogue_helpers import (
    get_cached_all_datasets,
    get_cached_dataset_dict,
    get_cached_schema_json,
)
from frontend.detail_context import (
    build_chart_groups,
    build_dataset_dcat_rows,
    build_distribution_dcat_rows,
    find_distribution_with_dataset,
    normalise_stat_charts,
    normalise_tables,
)
from frontend.filtering import FilterState, build_sidebar_context, filter_datasets
from frontend.presentation_dtos import FrontendStatChartDTO, FrontendTableDTO
from shared.export import build_jsonld, build_turtle, has_distributions
from shared.services import UnifiedCatalogService
from ticketing.cart import CartService as CartService

PAGE_SIZE = 15


def page_not_found(request, exception):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, '404.html', status=404)


class CatalogueIndexView(LoginRequiredMixin, View):
    """Main catalogue page — server-side filtered & paginated."""

    def get(self, request):
        service = UnifiedCatalogService()
        all_datasets = get_cached_all_datasets(service=service)
        schema_json = get_cached_schema_json(service=service)
        filter_state = FilterState.from_query_params(request.GET)

        filtered = filter_datasets(all_datasets, filter_state, service=service)
        paginator = Paginator(filtered, PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get('page', 1))

        total_count = len(all_datasets)
        dist_count = sum(len(ds.get('distributions', [])) for ds in all_datasets)

        sidebar_ctx = build_sidebar_context(filtered, filter_state=filter_state, service=service)

        context = {
            'page_obj': page_obj,
            'filter_params': filter_state.as_dict(),
            **sidebar_ctx,
            'total_count': total_count,
            'dist_count': dist_count,
            'schema_json': schema_json,
            'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
        }

        if request.headers.get('HX-Request'):
            return render(request, 'catalogue/components/_results.html', context)

        return render(request, 'catalogue/index.html', context)


class DatasetDetailView(LoginRequiredMixin, View):
    """Full detail page for a single dataset."""

    template_name = 'catalogue/dataset_detail.html'

    def get(self, request, app: str, name: str):
        service = UnifiedCatalogService()
        export_dataset = service.get_export_dataset(app, name)
        if export_dataset is None:
            raise Http404('Dataset not found')

        ds_dict = get_cached_dataset_dict(app, name, service=service)
        if ds_dict is None:
            raise Http404('Dataset not found')

        if not has_distributions(export_dataset):
            raise Http404('Dataset has no distributions')

        schema_json = get_cached_schema_json(service=service)
        dcat_rows = build_dataset_dcat_rows(schema_json, ds_dict)

        return render(
            request,
            self.template_name,
            {
                'dataset': ds_dict,
                'distributions': ds_dict['distributions'],
                'export_jsonld': build_jsonld(export_dataset),
                'schema_json': schema_json,
                'app': app,
                'dcat_rows': dcat_rows,
                'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
            },
        )


class DatasetRdfExportView(LoginRequiredMixin, View):
    """Authenticated Turtle export for a single dataset."""

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
    """Authenticated JSON-LD download for a single dataset."""

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
    """Detail page for a single distribution."""

    template_name = 'catalogue/distribution_detail.html'

    def get(self, request, app: str, name: str):
        service = UnifiedCatalogService()
        all_datasets = get_cached_all_datasets(service=service)

        distribution, dataset = find_distribution_with_dataset(all_datasets, app, name)

        if distribution is None:
            raise Http404('Distribution not found')

        schema_json = get_cached_schema_json(service=service)
        dcat_rows = build_distribution_dcat_rows(schema_json, distribution)

        tables: list[FrontendTableDTO] = normalise_tables(
            service.get_tables_with_columns(app, name)
        )
        charts: list[FrontendStatChartDTO] = normalise_stat_charts(
            service.get_stat_charts(app, name)
        )

        chart_groups = build_chart_groups(charts)

        return render(
            request,
            self.template_name,
            {
                'distribution': distribution,
                'dataset': dataset,
                'tables': tables,
                'charts': charts,
                'chart_groups': chart_groups,
                'schema_json': schema_json,
                'app': app,
                'dcat_rows': dcat_rows,
                'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
            },
        )
