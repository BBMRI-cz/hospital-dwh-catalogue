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

PAGE_SIZE = 20
_CACHE_TTL = 300          # 5 minutes
_CACHE_KEY_DATASETS = 'catalogue_all_datasets'
_CACHE_KEY_COUNTERS = 'catalogue_counters'
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

    # Default: all statuses active when none selected
    all_statuses = {'ready', 'raw', 'unavailable'}
    if not status_filter:
        status_filter = all_statuses

    result = []
    for ds in datasets:
        # Status
        if ds['status'] not in status_filter:
            continue
        # Source
        if source_filter and ds.get('source') not in source_filter:
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
        counters: dict | None = cache.get(_CACHE_KEY_COUNTERS)

        if all_datasets is None or counters is None:
            all_datasets = [
                _dataset_to_dict(ds) for ds in service.get_datasets_with_distributions()
            ]

            kw_counter:     Counter = Counter()
            src_counter:    Counter = Counter()
            rh_counter:     Counter = Counter()
            hc_counter:     Counter = Counter()
            status_counter: Counter = Counter()

            for ds in all_datasets:
                for kw in ds.get('keywords', []):
                    if kw:
                        kw_counter[kw] += 1
                if ds.get('source'):
                    src_counter[ds['source']] += 1
                if ds.get('rights_holder'):
                    rh_counter[ds['rights_holder']] += 1
                if ds.get('health_category'):
                    hc_counter[ds['health_category']] += 1
                status_counter[ds['status']] += 1

            counters = {
                'kw':     kw_counter,
                'src':    src_counter,
                'rh':     rh_counter,
                'hc':     hc_counter,
                'status': status_counter,
            }

            cache.set(_CACHE_KEY_DATASETS, all_datasets, _CACHE_TTL)
            cache.set(_CACHE_KEY_COUNTERS, counters, _CACHE_TTL)
        else:
            kw_counter     = counters['kw']
            src_counter    = counters['src']
            rh_counter     = counters['rh']
            hc_counter     = counters['hc']
            status_counter = counters['status']

        schema_json = cache.get_or_set(_CACHE_KEY_SCHEMA, service.get_schema_json, _CACHE_TTL)

        # ── Active filter state ──────────────────────────────────────────────
        get = request.GET
        q               = get.get('q', '')
        active_status   = set(get.getlist('status'))
        active_keywords = set(get.getlist('keywords'))
        active_sources  = set(get.getlist('source'))
        active_rights   = set(get.getlist('rights_holder'))
        active_cats     = set(get.getlist('health_category'))

        filter_params = {
            'q':               q,
            'status':          active_status,
            'keywords':        active_keywords,
            'source':          active_sources,
            'rights_holder':   active_rights,
            'health_category': active_cats,
        }

        # ── Filter + paginate ────────────────────────────────────────────────
        filtered  = _filter_datasets(all_datasets, get)
        paginator = Paginator(filtered, PAGE_SIZE)
        page_obj  = paginator.get_page(get.get('page', 1))

        # ── Global stats ─────────────────────────────────────────────────────
        total_count   = len(all_datasets)
        active_count  = sum(1 for ds in all_datasets if ds['status'] != 'unavailable')
        unavail_count = status_counter.get('unavailable', 0)
        dist_count    = sum(len(ds.get('distributions', [])) for ds in all_datasets)

        return render(request, 'catalogue/index.html', {
            'page_obj':      page_obj,
            'filter_params': filter_params,
            # Sidebar checkbox groups
            'sidebar_keywords':          _make_sidebar_items(kw_counter, active_keywords),
            'sidebar_sources':           _make_sidebar_items(src_counter, active_sources),
            'sidebar_rights_holders':    _make_sidebar_items(rh_counter, active_rights),
            'sidebar_health_categories': _make_sidebar_items(hc_counter, active_cats),
            # Status bar counts
            'sidebar_counts': {
                'ready':       status_counter.get('ready', 0),
                'raw':         status_counter.get('raw', 0),
                'unavailable': status_counter.get('unavailable', 0),
            },
            # Hero stats
            'total_count':   total_count,
            'active_count':  active_count,
            'unavail_count': unavail_count,
            'dist_count':    dist_count,
            # Schema modal
            'schema_json':   json.dumps(schema_json),
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
            'schema_json':  json.dumps(schema_json),
            'jsonld_str':   json.dumps(jsonld, indent=2, ensure_ascii=False),
            'source':       source,
        })

