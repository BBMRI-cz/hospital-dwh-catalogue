"""
Warehouse Views

Class-based views for the warehouse catalogue application.
"""

from __future__ import annotations

import json
from collections import Counter

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404
from django.views.generic import View
from django.shortcuts import render

from shared.services import UnifiedCatalogService
from ticketing.cart import CartService as CartService
from warehouse.models import Attribute, Distribution

PAGE_SIZE = 20
_CACHE_TTL = 300          # 5 minutes
_CACHE_KEY_DATASETS = 'catalogue_all_datasets'
_CACHE_KEY_SCHEMA   = 'catalogue_schema_json'


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
        'source': ds.source,
        'name': ds.name,
        'title': ds.title or ds.name,
        'version': ds.version,
        'description': ds.description,
        'theme': ds.theme,
        'publisher': ds.publisher_name,
        'license': ds.license,
        'conformed_to': ds.conformed_to,
        'issued': ds.issued,
        'modified': ds.modified,
        'keywords': _parse_keywords(ds.keyword),
        'source_uri': ds.source_uri,
        'creator': ds.creator,
        'contact_email': ds.contact_point_email,
        'rights_holder': ds.rights_holder,
        'provenance': ds.provenance,
        'catalog': ds.catalog_name,
        'access_rights': ds.access_rights,
        'applicable_legislation': ds.applicable_legislation,
        'health_category': ds.health_category,
        'hdab': ds.hdab_name,
        'status': _derive_status(ds.access_rights),
        'distributions': [
            {
                'source': d.source,
                'name': d.name,
                'title': d.title or d.name,
                'description': d.description,
                'access_url': d.access_url,
                'applicable_legislation': d.applicable_legislation,
                'format': d.format,
                'conformed_to': d.conformed_to,
                'byte_size': d.byte_size,
                'rights': d.rights,
                'issued': d.issued,
                'modified': d.modified,
                'db_layer': getattr(d, 'db_layer', None),
            }
            for d in dists
        ],
    }


def _build_jsonld(ds_dict: dict) -> dict:
    """Build a Health DCAT-AP JSON-LD document from a serialised dataset dict."""
    base = 'https://katalog.mou.cz'
    return {
        '@context': {
            'dcat':         'http://www.w3.org/ns/dcat#',
            'dct':          'http://purl.org/dc/terms/',
            'healthdcatap': 'https://healthdataportal.eu/ns/health-dcat-ap#',
            'dpv':          'https://w3id.org/dpv#',
            'skos':         'http://www.w3.org/2004/02/skos/core#',
            'csvw':         'http://www.w3.org/ns/csvw#',
            'xsd':          'http://www.w3.org/2001/XMLSchema#',
            'foaf':         'http://xmlns.com/foaf/0.1/',
            'org':          'http://www.w3.org/ns/org#',
        },
        '@type': ['dcat:Dataset', 'healthdcatap:HealthDataset'],
        '@id': f"{base}/dataset/{ds_dict['source']}/{ds_dict['name']}",
        'dct:title': [{'@language': 'cs', '@value': ds_dict['title']}],
        'dct:description': [{'@language': 'cs', '@value': ds_dict.get('description') or ''}],
        'dcat:keyword': ds_dict.get('keywords', []),
        'dct:rightsHolder': {'@type': 'org:Organization', 'foaf:name': ds_dict.get('rights_holder') or ''},
        'dct:publisher': {'@type': 'org:Organization', 'foaf:name': ds_dict.get('publisher') or ''},
        'dct:accessRights': {'@id': ds_dict.get('access_rights') or ''},
        'healthdcatap:hasHealthCategory': {'@id': ds_dict.get('health_category') or ''},
        'dcatap:applicableLegislation': {'@id': ds_dict.get('applicable_legislation') or ''},
        'dcat:distribution': [
            {
                '@type': ['dcat:Distribution', 'healthdcatap:HealthDistribution'],
                '@id': f"{base}/distribution/{d['name']}",
                'dct:title': [{'@language': 'cs', '@value': d['title']}],
                'dcat:accessURL': {'@id': d.get('access_url') or ''},
                'dct:format': d.get('format') or '',
                'dcatap:applicableLegislation': {'@id': d.get('applicable_legislation') or ''},
                **(
                    {'healthdcatap:dbLayer': d['db_layer']}
                    if d.get('db_layer') else {}
                ),
            }
            for d in ds_dict.get('distributions', [])
        ],
    }


def _filter_datasets(datasets: list, get_params) -> list:
    """Apply server-side filters from GET params to a list of dataset dicts."""
    q              = get_params.get('q', '').strip().lower()
    status_filter  = set(get_params.getlist('status'))
    keyword_filter = {k.lower() for k in get_params.getlist('keywords')}
    source_filter  = set(get_params.getlist('source'))
    rights_filter  = set(get_params.getlist('rights_holder'))
    cat_filter     = set(get_params.getlist('health_category'))
    theme_filter   = set(get_params.getlist('theme'))
    column_filter  = set(get_params.getlist('column'))

    # Default: all statuses active when none selected
    all_statuses = {'ready', 'raw', 'unavailable'}
    if not status_filter:
        status_filter = all_statuses

    # Resolve column filter → matching dataset names via Attribute + Distribution
    matching_dataset_names: frozenset | None = None
    if column_filter:
        dist_names = (
            Attribute.objects.using('metadata_db')
            .filter(title__in=column_filter)
            .values_list('distribution_name', flat=True)
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
        if source_filter and ds.get('source_uri') not in source_filter:
            continue
        # Keywords (ANY match)
        if keyword_filter:
            ds_kws = {k.lower() for k in ds.get('keywords', [])}
            if not keyword_filter.intersection(ds_kws):
                continue
        # Rights holder
        if rights_filter and ds.get('rights_holder') not in rights_filter:
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
            haystack = ' '.join([
                ds.get('title') or '',
                ds.get('description') or '',
                ds.get('rights_holder') or '',
                ds.get('source_uri') or '',
                ds.get('health_category') or '',
                ' '.join(ds.get('keywords', [])),
                ' '.join(d.get('title', '') for d in ds.get('distributions', [])),
            ]).lower()
            if q not in haystack:
                continue
        result.append(ds)

    return result


# ── Views ─────────────────────────────────────────────────────────────────────

def _make_sidebar_items(counter: Counter, active: set) -> list[dict]:
    """Build [{value, count, checked}] dicts for sidebar checkbox groups."""
    return [
        {'value': v, 'count': counter[v], 'checked': v in active}
        for v in sorted(counter)
        if v
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
        q               = get.get('q', '')
        active_status   = set(get.getlist('status'))
        active_keywords = set(get.getlist('keywords'))
        active_sources  = set(get.getlist('source'))
        active_rights   = set(get.getlist('rights_holder'))
        active_cats     = set(get.getlist('health_category'))
        active_themes   = set(get.getlist('theme'))
        active_columns  = set(get.getlist('column'))

        filter_params = {
            'q':               q,
            'status':          active_status,
            'keywords':        active_keywords,
            'source':          active_sources,
            'rights_holder':   active_rights,
            'health_category': active_cats,
            'theme':           active_themes,
            'column':          active_columns,
        }

        # ── Filter + paginate ────────────────────────────────────────────────
        filtered  = _filter_datasets(all_datasets, get)
        paginator = Paginator(filtered, PAGE_SIZE)
        page_obj  = paginator.get_page(get.get('page', 1))

        # ── Global stats (unfiltered) ─────────────────────────────────────────
        total_count = len(all_datasets)
        dist_count  = sum(len(ds.get('distributions', [])) for ds in all_datasets)

        # ── Sidebar counters (computed from filtered results) ─────────────────
        kw_counter:     Counter = Counter()
        src_counter:    Counter = Counter()
        rh_counter:     Counter = Counter()
        hc_counter:     Counter = Counter()
        theme_counter:  Counter = Counter()
        status_counter: Counter = Counter()

        for ds in filtered:
            for kw in ds.get('keywords', []):
                if kw:
                    kw_counter[kw] += 1
            if ds.get('source_uri'):
                src_counter[ds['source_uri']] += 1
            if ds.get('rights_holder'):
                rh_counter[ds['rights_holder']] += 1
            if ds.get('health_category'):
                hc_counter[ds['health_category']] += 1
            if ds.get('theme'):
                theme_counter[ds['theme']] += 1
            status_counter[ds['status']] += 1

        # ── Distribution column counter (from filtered datasets) ──────────────
        col_counter: Counter = Counter()
        filtered_dist_names = [
            d['name']
            for ds in filtered if ds.get('source') == 'warehouse'
            for d in ds.get('distributions', [])
        ]
        if filtered_dist_names:
            dist_to_dataset: dict[str, str] = {
                d['name']: ds['name']
                for ds in filtered
                for d in ds.get('distributions', [])
            }
            seen_col_ds: set[tuple] = set()
            attr_rows = (
                Attribute.objects.using('metadata_db')
                .filter(distribution_name__in=filtered_dist_names)
                .exclude(title='')
                .filter(title__isnull=False)
                .values_list('title', 'distribution_name')
                .distinct()
            )
            for title, dist_name in attr_rows:
                ds_name = dist_to_dataset.get(dist_name)
                if ds_name and (title, ds_name) not in seen_col_ds:
                    col_counter[title] += 1
                    seen_col_ds.add((title, ds_name))

        return render(request, 'catalogue/index.html', {
            'page_obj':      page_obj,
            'filter_params': filter_params,
            # Sidebar checkbox groups
            'sidebar_keywords':          _make_sidebar_items(kw_counter, active_keywords),
            'sidebar_sources':           _make_sidebar_items(src_counter, active_sources),
            'sidebar_rights_holders':    _make_sidebar_items(rh_counter, active_rights),
            'sidebar_health_categories': _make_sidebar_items(hc_counter, active_cats),
            'sidebar_themes':            _make_sidebar_items(theme_counter, active_themes),
            'sidebar_columns':           _make_sidebar_items(col_counter, active_columns),
            # Status bar counts
            'sidebar_counts': {
                'ready':       status_counter.get('ready', 0),
                'raw':         status_counter.get('raw', 0),
                'unavailable': status_counter.get('unavailable', 0),
            },
            # Hero stats
            'total_count':   total_count,
            'dist_count':    dist_count,
            # Schema modal
            'schema_json':   schema_json,
            # Cart state
            'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
        })


class DatasetDetailView(LoginRequiredMixin, View):
    """Full detail page for a single dataset."""

    template_name = 'catalogue/dataset_detail.html'

    def get(self, request, source: str, name: str):
        service = UnifiedCatalogService()
        cache_key = f'dataset:{source}:{name}'
        ds_dict: dict | None = cache.get(cache_key)

        if ds_dict is None:
            ds, dist_objs = service.get_single_dataset(source, name)
            if ds is None:
                raise Http404('Dataset not found')
            if not ds.distributions:
                ds.distributions = dist_objs
            ds_dict = _dataset_to_dict(ds)
            cache.set(cache_key, ds_dict, _CACHE_TTL)

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)
        jsonld = _build_jsonld(ds_dict)

        return render(request, self.template_name, {
            'dataset':      ds_dict,
            'distributions': ds_dict['distributions'],
            'schema_json':  schema_json,
            'jsonld_str':   json.dumps(jsonld, indent=2, ensure_ascii=False),
            'source':       source,
            'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
        })


class DistributionDetailView(LoginRequiredMixin, View):
    """Detail page for a single distribution."""

    template_name = 'catalogue/distribution_detail.html'

    def get(self, request, source: str, name: str):
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
                if dist['source'] == source and dist['name'] == name:
                    distribution = dist
                    dataset = ds
                    break
            if distribution:
                break

        if distribution is None:
            raise Http404('Distribution not found')

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)

        return render(request, self.template_name, {
            'distribution': distribution,
            'dataset':      dataset,
            'columns':      [],   # Column model not yet implemented
            'schema_json':  schema_json,
            'source':       source,
            'cart_dataset_ids': {item['name'] for item in CartService.get(request.session)},
        })

