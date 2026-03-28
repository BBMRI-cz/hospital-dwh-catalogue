"""
Warehouse Views

Class-based views for the warehouse catalogue application.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections import Counter

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.views.generic import View

from shared.dtos import UnifiedDataset, UnifiedDistribution
from shared.export import build_jsonld, has_distributions
from shared.services import UnifiedCatalogService
from ticketing.cart import CartService as CartService
from warehouse.models import Column, Distribution

PAGE_SIZE = 15
_CACHE_TTL = 300  # 5 minutes
_CACHE_KEY_DATASETS = 'catalogue_all_datasets'
_CACHE_KEY_SCHEMA = 'catalogue_schema_json'



def page_not_found(request, exception):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, '404.html', status=404)

def _to_snake(camel: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel).lower()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_keywords(keyword_str: str | None) -> list[str]:
    """Parse a comma-separated keyword string into a clean list."""
    return [k.strip() for k in (keyword_str or '').split(',') if k.strip()]


def _derive_status(access_rights: str | None) -> str:
    """
    Derive a simple three-way status from an access-rights URI or label.

    ready       → PUBLIC / open access
    raw         → RESTRICTED / limited / unknown
    unavailable → NON_PUBLIC / closed
    """
    if not access_rights:
        return 'raw'
    ar = access_rights.upper()
    if 'PUBLIC' in ar and 'NON' not in ar:
        return 'ready'
    if 'NON_PUBLIC' in ar or 'NONPUBLIC' in ar or 'CLOSED' in ar:
        return 'unavailable'
    return 'raw'


def _dataset_to_dict(ds) -> dict:
    """Serialise a UnifiedDataset DTO (with .distributions) to a plain dict."""
    dists = getattr(ds, 'distributions', [])
    return {
        'title': ds.title or ds.name,
        'access_rights': ds.access_rights,
        'version': ds.version,
        'conforms_to': ds.conforms_to,
        'theme': ds.theme,
        'publisher': ds.publisher,
        'applicable_legislation': ds.applicable_legislation,
        'health_category': ds.health_category,
        'hdab': ds.hdab,
        'source': ds.source,
        'creator': ds.creator,
        'issued': ds.issued,
        'modified': ds.modified,
        'contact_point': ds.contact_point,
        'custodian': ds.custodian,
        'provenance': ds.provenance,
        # Non-DCAT fields needed elsewhere (routing, filtering, display)
        'app': ds.app,
        'name': ds.name,
        'description': ds.description,
        'keywords': _parse_keywords(ds.keyword),
        'catalog': ds.catalog_name,
        'status': _derive_status(ds.access_rights),
        'distributions': [
            {
                'app': d.app,
                'name': d.name,
                'title': d.title or d.name,
                'description': d.description,
                'access_url': d.access_url,
                'applicable_legislation': d.applicable_legislation,
                'format': d.format,
                'conforms_to': d.conforms_to,
                'byte_size': d.byte_size,
                'rights': d.rights,
                'issued': d.issued,
                'modified': d.modified,
                'licence': d.licence,
                'db_layer': getattr(d, 'db_layer', None),
            }
            for d in dists
        ],
    }


def _filter_datasets(datasets: list, get_params) -> list:
    """Apply server-side filters from GET params to a list of dataset dicts."""
    q = get_params.get('q', '').strip().lower()
    status_filter = set(get_params.getlist('status'))
    keyword_filter = {k.lower() for k in get_params.getlist('keywords')}
    source_filter = set(get_params.getlist('source'))  # dct:source URI filter
    custodian_filter = set(get_params.getlist('custodian'))
    cat_filter = set(get_params.getlist('health_category'))
    theme_filter = set(get_params.getlist('theme'))
    column_filter = set(get_params.getlist('column'))

    # Default: all statuses active when none selected
    all_statuses = {'ready', 'raw', 'unavailable'}
    if not status_filter:
        status_filter = all_statuses

    # Resolve column filter → matching dataset names via Column + Distribution
    matching_dataset_names: frozenset | None = None
    if column_filter:
        dist_names = (
            Column.objects.using('metadata_db')
            .filter(title__in=column_filter)
            .values_list('table__distribution_id', flat=True)
            .distinct()
        )
        dataset_names = (
            Distribution.objects.using('metadata_db')
            .filter(name__in=dist_names)
            .values_list('dataset_name', flat=True)
            .distinct()
        )
        matching_dataset_names = frozenset(dataset_names)

    result = []
    for ds in datasets:
        # Status
        if ds['status'] not in status_filter:
            continue
        # Source (dct:source URI)
        if source_filter and ds.get('source') not in source_filter:
            continue
        # Keywords (ANY match)
        if keyword_filter:
            ds_kws = {k.lower() for k in ds.get('keywords', [])}
            if not keyword_filter.intersection(ds_kws):
                continue
        # Custodian
        if custodian_filter and ds.get('custodian') not in custodian_filter:
            continue
        # Health category
        if cat_filter and ds.get('health_category') not in cat_filter:
            continue
        # Theme
        if theme_filter and ds.get('theme') not in theme_filter:
            continue
        # Distribution columns
        if matching_dataset_names is not None and ds.get('name') not in matching_dataset_names:
            continue
        # Text search
        if q:
            haystack = ' '.join(
                [
                    ds.get('title') or '',
                    ds.get('description') or '',
                    ds.get('custodian') or '',
                    ds.get('source') or '',
                    ds.get('health_category') or '',
                    ' '.join(ds.get('keywords', [])),
                    ' '.join(d.get('title', '') for d in ds.get('distributions', [])),
                ]
            ).lower()
            if q not in haystack:
                continue
        result.append(ds)

    return result


# ── Views ─────────────────────────────────────────────────────────────────────


def _agent_label(name: str) -> str:
    """Human-readable label for an agent identifier, e.g. AGENT_DWH → DWH."""
    label = re.sub(r'AGENT_', '', name, flags=re.IGNORECASE)
    return label.replace('_', ' ').strip() or name


def _health_category_label(value: str) -> str:
    """Human-readable label for a health_category code, e.g. patient_data → Patient data."""
    return value.replace('_', ' ').capitalize()


def _theme_label(value: str) -> str:
    """Human-readable label for a theme URI, e.g. .../MESH/D000293 → MESH / D000293."""
    # Strip trailing slash then take the last two path segments
    parts = value.rstrip('/').rsplit('/', 2)
    if len(parts) >= 3:
        return f'{parts[-2]} / {parts[-1]}'
    return parts[-1] or value


def _make_sidebar_items(
    counter: Counter,
    active: set,
    label_fn: object = None,
) -> list[dict]:
    """Build [{value, label, count, checked}] dicts for sidebar checkbox groups.

    Active (checked) values are always included even when their count drops to
    zero after another filter narrows the result set, and they are sorted to the
    top so the user never loses track of what they selected.

    label_fn, if provided, maps a raw value to a display label.
    """
    all_values = (set(counter) | active) - {''}
    return [
        {
            'value': v,
            'label': label_fn(v) if label_fn else v,
            'count': counter.get(v, 0),
            'checked': v in active,
        }
        for v in sorted(all_values, key=lambda v: (v not in active, v.lower()))
    ]


class CatalogueIndexView(LoginRequiredMixin, View):
    """Main catalogue page — server-side filtered & paginated."""

    def get(self, request):
        service = UnifiedCatalogService()

        all_datasets: list[dict] = cache.get(_CACHE_KEY_DATASETS)

        if all_datasets is None:
            all_datasets = [
                _dataset_to_dict(ds) for ds in service.get_datasets_with_distributions()
            ]
            cache.set(_CACHE_KEY_DATASETS, all_datasets, _CACHE_TTL)

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)

        # ── Active filter state ──────────────────────────────────────────────
        get = request.GET
        q = get.get('q', '')
        active_status = set(get.getlist('status'))
        active_keywords = set(get.getlist('keywords'))
        active_sources = set(get.getlist('source'))
        active_custodians = set(get.getlist('custodian'))
        active_cats = set(get.getlist('health_category'))
        active_themes = set(get.getlist('theme'))
        active_columns = set(get.getlist('column'))

        filter_params = {
            'q': q,
            'status': active_status,
            'keywords': active_keywords,
            'source': active_sources,
            'custodian': active_custodians,
            'health_category': active_cats,
            'theme': active_themes,
            'column': active_columns,
        }

        # ── Filter + paginate ────────────────────────────────────────────────
        filtered = _filter_datasets(all_datasets, get)
        paginator = Paginator(filtered, PAGE_SIZE)
        page_obj = paginator.get_page(get.get('page', 1))

        # ── Global stats (unfiltered) ─────────────────────────────────────────
        total_count = len(all_datasets)
        dist_count = sum(len(ds.get('distributions', [])) for ds in all_datasets)

        # ── Sidebar counters (computed from filtered results) ─────────────────
        kw_counter: Counter = Counter()
        src_counter: Counter = Counter()
        custodian_counter: Counter = Counter()
        hc_counter: Counter = Counter()
        theme_counter: Counter = Counter()
        status_counter: Counter = Counter()

        for ds in filtered:
            for kw in ds.get('keywords', []):
                if kw:
                    kw_counter[kw] += 1
            if ds.get('source'):
                src_counter[ds['source']] += 1
            if ds.get('custodian'):
                custodian_counter[ds['custodian']] += 1
            if ds.get('health_category'):
                hc_counter[ds['health_category']] += 1
            if ds.get('theme'):
                theme_counter[ds['theme']] += 1
            status_counter[ds['status']] += 1

        # ── Distribution column counter (from filtered datasets) ──────────────
        col_counter: Counter = Counter()
        filtered_dist_names = [
            d['name']
            for ds in filtered
            if ds.get('app') == 'warehouse'
            for d in ds.get('distributions', [])
        ]
        if filtered_dist_names:
            dist_to_dataset: dict[str, str] = {
                d['name']: ds['name'] for ds in filtered for d in ds.get('distributions', [])
            }
            seen_col_ds: set[tuple] = set()
            attr_rows = (
                Column.objects.using('metadata_db')
                .filter(table__distribution__in=filtered_dist_names)
                .exclude(title='')
                .values_list('title', 'table__distribution_id')
                .distinct()
            )
            for title, dist_name in attr_rows:
                ds_name = dist_to_dataset.get(dist_name)
                if ds_name and (title, ds_name) not in seen_col_ds:
                    col_counter[title] += 1
                    seen_col_ds.add((title, ds_name))

        return render(
            request,
            'catalogue/index.html',
            {
                'page_obj': page_obj,
                'filter_params': filter_params,
                # Sidebar checkbox groups
                'sidebar_keywords': _make_sidebar_items(kw_counter, active_keywords),
                'sidebar_sources': _make_sidebar_items(src_counter, active_sources),
                'sidebar_custodians': _make_sidebar_items(custodian_counter, active_custodians, label_fn=_agent_label),
                'sidebar_health_categories': _make_sidebar_items(hc_counter, active_cats, label_fn=_health_category_label),
                'sidebar_themes': _make_sidebar_items(theme_counter, active_themes, label_fn=_theme_label),
                'sidebar_columns': _make_sidebar_items(col_counter, active_columns),
                # Status bar counts
                'sidebar_counts': {
                    'ready': status_counter.get('ready', 0),
                    'raw': status_counter.get('raw', 0),
                    'unavailable': status_counter.get('unavailable', 0),
                },
                # Hero stats
                'total_count': total_count,
                'dist_count': dist_count,
                # Schema modal
                'schema_json': schema_json,
                # Cart state
                'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
            },
        )


class DatasetDetailView(LoginRequiredMixin, View):
    """Full detail page for a single dataset."""

    template_name = 'catalogue/dataset_detail.html'

    def get(self, request, app: str, name: str):
        service = UnifiedCatalogService()
        cache_key = f'dataset:{app}:{name}'
        ds_dict: dict | None = cache.get(cache_key)

        if ds_dict is None:
            ds, dist_objs = service.get_single_dataset(app, name)
            if ds is None:
                raise Http404('Dataset not found')
            if not ds.distributions:
                ds.distributions = dist_objs
            ds_dict = _dataset_to_dict(ds)
            cache.set(cache_key, ds_dict, _CACHE_TTL)

        if not has_distributions(ds_dict):
            raise Http404('Dataset has no distributions')

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)
        jsonld = build_jsonld(ds_dict)

        # Build an inverse schema map: DTO field name → DCAT term.
        # DTO fields are declared in display order, so iteration order IS display order.
        _inverse = {_to_snake(info['local_name']): term for term, info in schema_json.items()}

        dcat_rows = [
            (
                _inverse[f.name],
                schema_json[_inverse[f.name]].get('label', _inverse[f.name]),
                ds_dict.get(f.name),
            )
            for f in dataclasses.fields(UnifiedDataset)
            if f.name in _inverse
        ]

        return render(
            request,
            self.template_name,
            {
                'dataset': ds_dict,
                'distributions': ds_dict['distributions'],
                'schema_json': schema_json,
                'jsonld_str': json.dumps(jsonld, indent=2, ensure_ascii=False),
                'app': app,
                'dcat_rows': dcat_rows,
                'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
            },
        )


class DistributionDetailView(LoginRequiredMixin, View):
    """Detail page for a single distribution."""

    template_name = 'catalogue/distribution_detail.html'

    def get(self, request, app: str, name: str):
        service = UnifiedCatalogService()

        all_datasets: list[dict] | None = cache.get(_CACHE_KEY_DATASETS)
        if all_datasets is None:
            all_datasets = [
                _dataset_to_dict(ds) for ds in service.get_datasets_with_distributions()
            ]
            cache.set(_CACHE_KEY_DATASETS, all_datasets, _CACHE_TTL)

        distribution: dict | None = None
        dataset: dict | None = None
        for ds in all_datasets:
            for dist in ds.get('distributions', []):
                if dist['app'] == app and dist['name'] == name:
                    distribution = dist
                    dataset = ds
                    break
            if distribution:
                break

        if distribution is None:
            raise Http404('Distribution not found')

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)

        # Build an inverse schema map: DTO field name → DCAT term.
        _inverse = {_to_snake(info['local_name']): term for term, info in schema_json.items()}

        dcat_rows = [
            (
                _inverse[f.name],
                schema_json[_inverse[f.name]].get('label', _inverse[f.name]),
                distribution.get(f.name),
            )
            for f in dataclasses.fields(UnifiedDistribution)
            if f.name in _inverse
        ]

        col_qs = (
            Column.objects.using('metadata_db')
            .filter(table__distribution_id=name)
            .select_related('table')
            .order_by('var_order', 'name')
        )
        columns = [
            {
                'name': c.name,
                'title': c.title,
                'description': c.description,
                'datatype': c.datatype,
                'type_r': c.type_r,
                'key_db': c.key_db,
                'property_url': c.property_url,
            }
            for c in col_qs
        ]

        # For Fair Genomes distributions: attach stat counts grouped by column.
        # fair_genomes.Table rows are linked to this distribution via their
        # distribution FK; StatResult rows are keyed by table_name + column_name.
        stat_groups = None
        if app == 'fair_genomes':
            from collections import defaultdict

            from fair_genomes.models import StatResult
            from fair_genomes.models import Table as FGTable

            fg_table_names = list(
                FGTable.objects.using('fair_genomes_db')
                .filter(distribution_id=name)
                .values_list('name', flat=True)
            )
            if fg_table_names:
                stat_qs = StatResult.objects.using('fair_genomes_db').filter(
                    table_name__in=fg_table_names,
                    count__isnull=False,
                )
                grouped: dict = defaultdict(list)
                for sr in stat_qs:
                    grouped[(sr.table_name, sr.column_name)].append(sr)
                if grouped:
                    stat_groups = grouped

        return render(
            request,
            self.template_name,
            {
                'distribution': distribution,
                'dataset': dataset,
                'columns': columns,
                'schema_json': schema_json,
                'app': app,
                'dcat_rows': dcat_rows,
                'stat_groups': stat_groups,
                'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
            },
        )
