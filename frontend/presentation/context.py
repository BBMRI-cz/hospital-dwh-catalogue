"""Context builders for catalogue frontend views."""

from __future__ import annotations

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404

from frontend.presentation.cache import (
    get_cached_catalogue_snapshot,
    get_cached_dataset,
    get_cached_distribution_lookup,
    get_cached_schema_json,
)
from frontend.presentation.filters import FilterState, build_sidebar_context, filter_datasets
from frontend.presentation.mapping import (
    build_chart_groups,
    build_dataset_dcat_rows,
    build_distribution_dcat_rows,
    normalise_stat_charts,
    normalise_tables,
    serialise_chart_groups,
    serialise_stat_charts,
)
from shared.export import build_jsonld, has_distributions
from shared.services import UnifiedCatalogService
from ticketing.cart import CartService


def get_cart_dataset_ids(session) -> set[str]:
    return {item['name'] for item in CartService.get(session)}


def build_catalogue_index_context(request, *, service: UnifiedCatalogService | None = None) -> dict:
    catalog_service = service or UnifiedCatalogService()
    snapshot = get_cached_catalogue_snapshot(service=catalog_service)
    schema_json = get_cached_schema_json(service=catalog_service)
    filter_state = FilterState.from_query_params(request.GET)

    filtered = filter_datasets(snapshot.datasets, filter_state, service=catalog_service)
    paginator = Paginator(filtered, settings.CATALOGUE_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    sidebar_context = build_sidebar_context(
        filtered,
        filter_state=filter_state,
        service=catalog_service,
    )

    return {
        'page_obj': page_obj,
        'filter_params': filter_state,
        'sidebar_keywords': sidebar_context.sidebar_keywords,
        'sidebar_sources': sidebar_context.sidebar_sources,
        'sidebar_custodians': sidebar_context.sidebar_custodians,
        'sidebar_health_categories': sidebar_context.sidebar_health_categories,
        'sidebar_themes': sidebar_context.sidebar_themes,
        'sidebar_columns': sidebar_context.sidebar_columns,
        'sidebar_counts': sidebar_context.sidebar_counts,
        'total_count': len(snapshot.datasets),
        'dist_count': snapshot.total_distribution_count,
        'schema_json': schema_json,
        'cart_dataset_ids': get_cart_dataset_ids(request.session),
    }


def build_dataset_detail_context(
    request,
    *,
    app: str,
    name: str,
    service: UnifiedCatalogService | None = None,
) -> dict:
    catalog_service = service or UnifiedCatalogService()
    export_dataset = catalog_service.get_export_dataset(app, name)
    if export_dataset is None:
        raise Http404('Dataset not found')

    dataset = get_cached_dataset(app, name, service=catalog_service)
    if dataset is None:
        raise Http404('Dataset not found')

    if not has_distributions(export_dataset):
        raise Http404('Dataset has no distributions')

    schema_json = get_cached_schema_json(service=catalog_service)
    return {
        'dataset': dataset,
        'distributions': dataset.distributions,
        'export_jsonld': build_jsonld(export_dataset),
        'schema_json': schema_json,
        'app': app,
        'dcat_rows': build_dataset_dcat_rows(schema_json, dataset),
        'cart_dataset_ids': get_cart_dataset_ids(request.session),
    }


def build_distribution_detail_context(
    request,
    *,
    app: str,
    name: str,
    service: UnifiedCatalogService | None = None,
) -> dict:
    catalog_service = service or UnifiedCatalogService()
    lookup = get_cached_distribution_lookup(app, name, service=catalog_service)
    if lookup is None:
        raise Http404('Distribution not found')

    schema_json = get_cached_schema_json(service=catalog_service)
    tables = normalise_tables(catalog_service.get_tables_with_columns(app, name))
    charts = normalise_stat_charts(catalog_service.get_stat_charts(app, name))
    chart_groups = build_chart_groups(charts)

    return {
        'distribution': lookup.distribution,
        'dataset': lookup.dataset,
        'tables': tables,
        'charts': serialise_stat_charts(charts),
        'chart_groups': serialise_chart_groups(chart_groups),
        'schema_json': schema_json,
        'app': app,
        'dcat_rows': build_distribution_dcat_rows(schema_json, lookup.distribution),
        'cart_dataset_ids': get_cart_dataset_ids(request.session),
    }
