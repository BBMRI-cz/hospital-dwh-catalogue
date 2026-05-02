"""
Fair Genomes Admin Configuration
"""

import json
import logging
import time

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import Dataset, Distribution, FairGenomesSyncState, StatDefinition
from fair_genomes.services.sync_state import (
    get_state_map,
    mark_failed,
    mark_started,
    mark_success,
    stats_report_summary,
)

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_KEY = 'fg_molgenis_schema'
_SCHEMA_CACHE_TTL = 300  # 5 minutes
_RDF_INVENTORY_CACHE_KEY_PREFIX = 'fg_rdf_inventory'
_RDF_INVENTORY_CACHE_TTL = 300  # 5 minutes


def _sync_report_status_label(status: str) -> str:
    labels = {
        'complete': _('Complete'),
        'partial': _('Partial'),
        'failed': _('Failed'),
        'skipped': _('Skipped'),
        'nothing_saved': _('Nothing saved'),
        'unknown': _('Unknown'),
    }
    return str(labels.get(status, status))


def _get_molgenis_schema() -> dict[str, list[str]]:
    """Return cached MOLGENIS schema or fetch live."""
    cached = cache.get(_SCHEMA_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        from fair_genomes.services.fair_genomes_service import FairGenomesService

        svc = FairGenomesService()
        schema = svc.introspect_molgenis_schema()
    except Exception:
        logger.exception('Failed to introspect MOLGENIS schema')
        schema = {}

    cache.set(_SCHEMA_CACHE_KEY, schema, _SCHEMA_CACHE_TTL)
    return schema


def _rdf_inventory_cache_key(url: str) -> str:
    return f'{_RDF_INVENTORY_CACHE_KEY_PREFIX}:{url}'


def _get_rdf_source_inventory() -> dict:
    """Return cached RDF source dataset/distribution names without writing to DB."""
    url = getattr(settings, 'FAIR_GENOMES_RDF_URL', '')
    if not url:
        return {
            'status': 'not_configured',
            'source_url': '',
            'datasets': set(),
            'distributions': set(),
            'error': 'FAIR_GENOMES_RDF_URL is not configured.',
        }

    cache_key = _rdf_inventory_cache_key(url)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from rdflib import Graph

        from fair_genomes.services.client import detect_rdf_format, fetch_rdf
        from fair_genomes.services.parser import parse_raw_records

        response = fetch_rdf(url, timeout=(5, 20))
        graph = Graph()
        graph.parse(data=response.text, format=detect_rdf_format(response))
        records = parse_raw_records(graph)
        inventory = {
            'status': 'available',
            'source_url': url,
            'datasets': {
                str(record.values.get('name'))
                for record in records.get('Dataset', [])
                if record.values.get('name')
            },
            'distributions': {
                str(record.values.get('name'))
                for record in records.get('Distribution', [])
                if record.values.get('name')
            },
            'error': '',
        }
    except Exception as exc:
        logger.warning('Failed to inspect FAIR Genomes RDF source inventory: %s', exc)
        inventory = {
            'status': 'unavailable',
            'source_url': url,
            'datasets': set(),
            'distributions': set(),
            'error': str(exc),
        }

    cache.set(cache_key, inventory, _RDF_INVENTORY_CACHE_TTL)
    return inventory


def _clear_live_rdf_inventory_cache() -> None:
    url = getattr(settings, 'FAIR_GENOMES_RDF_URL', '')
    if url:
        cache.delete(_rdf_inventory_cache_key(url))


def _get_rdf_inventory_status() -> dict:
    inventory = _get_rdf_source_inventory()
    local_distribution_names = set(
        Distribution.objects.using('fair_genomes_db').values_list('name', flat=True)
    )
    local_dataset_names = set(
        Dataset.objects.using('fair_genomes_db').values_list('name', flat=True)
    )

    live_distributions = set(inventory.get('distributions') or set())
    live_datasets = set(inventory.get('datasets') or set())
    missing_local_distributions = sorted(live_distributions - local_distribution_names)
    stale_local_distributions = sorted(local_distribution_names - live_distributions)

    return {
        **inventory,
        'local_dataset_count': len(local_dataset_names),
        'local_distribution_count': len(local_distribution_names),
        'live_dataset_count': len(live_datasets),
        'live_distribution_count': len(live_distributions),
        'missing_local_distributions': missing_local_distributions[:10],
        'missing_local_distribution_count': len(missing_local_distributions),
        'stale_local_distributions': stale_local_distributions[:10],
        'stale_local_distribution_count': len(stale_local_distributions),
    }


def _get_sync_state_context() -> list[FairGenomesSyncState]:
    states = get_state_map()
    return [
        states.get(
            source_type,
            FairGenomesSyncState(source_type=source_type),
        )
        for source_type in (
            FairGenomesSyncState.SourceType.RDF_METADATA,
            FairGenomesSyncState.SourceType.STATISTICS,
        )
    ]


class StatDefinitionForm(forms.ModelForm):
    """
    ModelForm for StatDefinition with dynamic choices from MOLGENIS
    introspection.  Falls back to free-text input if MOLGENIS is unreachable.
    """

    # Virtual field — not saved to the model; used only to filter the
    # distribution dropdown on the client side.
    dataset = forms.ChoiceField(
        required=False,
        label=_('Dataset'),
        help_text=_('Select a dataset to filter the distribution list.'),
    )

    class Meta:
        model = StatDefinition
        fields = [
            'distribution',
            'molgenis_table',
            'molgenis_column',
            'display_label',
            'sort_order',
            'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # -- Dataset choices ------------------------------------------------
        datasets = Dataset.objects.using('fair_genomes_db').order_by('title')
        dataset_choices = [('', '---------')] + [(ds.name, ds.title or ds.name) for ds in datasets]
        self.fields['dataset'].choices = dataset_choices

        # -- Distribution choices (with Dataset → Distribution label) --------
        distributions_qs = list(
            Distribution.objects.using('fair_genomes_db')
            .select_related('dataset_name')
            .order_by('dataset_name__title', 'title')
        )
        dist_choices = [('', '---------')] + [
            (
                d.name,
                f'{d.dataset_name.title or d.dataset_name_id} \u2192 {d.title or d.name}',
            )
            for d in distributions_qs
        ]
        # Mapping dist pk → dataset pk, embedded as JSON for client-side
        # filtering so JS knows which distributions belong to which dataset.
        dist_dataset_map = {d.name: d.dataset_name_id for d in distributions_qs}
        distribution_help_text = _('DCAT Distribution whose detail page should show this chart.')
        rdf_status = _get_rdf_inventory_status()
        if rdf_status['status'] == 'available' and rdf_status['missing_local_distribution_count']:
            distribution_help_text = _(
                'DCAT Distribution whose detail page should show this chart. '
                'The RDF source contains %(count)d distribution(s) that are not yet available '
                'in the local catalogue; run "Check and synchronise FAIR Genomes metadata" '
                'before configuring charts for them.'
            ) % {'count': rdf_status['missing_local_distribution_count']}
        elif rdf_status['status'] == 'unavailable':
            distribution_help_text = _(
                'DCAT Distribution whose detail page should show this chart. '
                'The RDF source could not be checked; showing locally synchronised values.'
            )
        elif rdf_status['status'] == 'not_configured':
            distribution_help_text = _(
                'DCAT Distribution whose detail page should show this chart. '
                'FAIR_GENOMES_RDF_URL is not configured; showing locally synchronised values.'
            )

        self.fields['distribution'] = forms.ChoiceField(
            choices=dist_choices,
            label=_('Distribution'),
            help_text=distribution_help_text,
            widget=forms.Select(attrs={'data-dist-map': json.dumps(dist_dataset_map)}),
        )

        # -- Pre-populate when editing an existing instance ------------------
        if self.instance and self.instance.pk:
            self.fields['distribution'].initial = self.instance.distribution_id
            # Derive the current dataset from the chosen distribution.
            current_dist = next(
                (d for d in distributions_qs if d.name == self.instance.distribution_id),
                None,
            )
            if current_dist:
                self.fields['dataset'].initial = current_dist.dataset_name_id

        schema = _get_molgenis_schema()

        if schema:
            table_choices = [('', '---------')] + [(t, t) for t in sorted(schema.keys())]
            self.fields['molgenis_table'] = forms.ChoiceField(
                choices=table_choices,
                label=_('MOLGENIS table'),
                help_text=_('MOLGENIS table name, e.g. "sequencing"'),
            )

            # Build a flat list of all columns for the initial dropdown.
            # JavaScript on the admin page will filter based on the selected
            # table, but we need all choices available for validation.
            all_columns: list[tuple[str, str]] = [('', '---------')]
            for table_name, cols in sorted(schema.items()):
                for col in cols:
                    all_columns.append((col, f'{table_name} → {col}'))
            self.fields['molgenis_column'] = forms.ChoiceField(
                choices=all_columns,
                label=_('MOLGENIS column'),
                help_text=_('Column name within the table.'),
            )

            # Store schema as JSON for client-side filtering.
            self._molgenis_schema = schema
        else:
            # MOLGENIS unreachable — build selects from values already in DB
            # so the fields always render as dropdowns rather than text inputs.
            existing_tables = sorted(
                StatDefinition.objects.using('fair_genomes_db')
                .values_list('molgenis_table', flat=True)
                .distinct()
            )
            existing_pairs = sorted(
                StatDefinition.objects.using('fair_genomes_db')
                .values_list('molgenis_table', 'molgenis_column')
                .distinct()
            )

            table_choices = [('', '---------')] + [(t, t) for t in existing_tables]
            col_choices: list[tuple[str, str]] = [('', '---------')] + [
                (col, f'{tbl} \u2192 {col}') for tbl, col in existing_pairs
            ]

            self.fields['molgenis_table'] = forms.ChoiceField(
                choices=table_choices,
                label=_('MOLGENIS table'),
                help_text=_('MOLGENIS is currently unreachable. Showing known values.'),
                required=False,
            )
            self.fields['molgenis_column'] = forms.ChoiceField(
                choices=col_choices,
                label=_('MOLGENIS column'),
                help_text=_('MOLGENIS is currently unreachable. Showing known values.'),
                required=False,
            )
            self._molgenis_schema = None

        # -- Field order: dataset → distribution → molgenis fields → rest ---
        desired_order = [
            'dataset',
            'distribution',
            'molgenis_table',
            'molgenis_column',
            'display_label',
            'sort_order',
            'is_active',
        ]
        self.fields = type(self.fields)(
            (k, self.fields[k]) for k in desired_order if k in self.fields
        )

    def clean_distribution(self):
        """Convert the chosen distribution name back to a Distribution instance."""
        name = self.cleaned_data.get('distribution')
        if not name:
            raise forms.ValidationError(_('This field is required.'))
        try:
            return Distribution.objects.using('fair_genomes_db').get(pk=name)
        except Distribution.DoesNotExist:
            raise forms.ValidationError(_('Select a valid choice. That choice is not available.'))


@admin.register(StatDefinition)
class StatDefinitionAdmin(admin.ModelAdmin):
    form = StatDefinitionForm
    fields = (
        'dataset',
        'distribution',
        'molgenis_table',
        'molgenis_column',
        'display_label',
        'sort_order',
        'is_active',
    )
    list_display = (
        'get_dataset',
        'distribution',
        'molgenis_table',
        'molgenis_column',
        'display_label',
        'is_active',
        'sort_order',
    )
    list_filter = ('is_active', 'distribution__dataset_name')
    list_editable = ('is_active', 'sort_order')
    ordering = ('distribution__dataset_name', 'distribution', 'sort_order')
    actions = ['sync_selected_stats']
    list_per_page = 50

    @admin.display(description=_('Dataset'), ordering='distribution__dataset_name')
    def get_dataset(self, obj):
        ds = obj.distribution.dataset_name
        return ds.title or ds.name

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('distribution__dataset_name')

    def _stat_result_exists(self, obj: StatDefinition) -> bool:
        from fair_genomes.models import StatResult

        return (
            StatResult.objects.using('fair_genomes_db')
            .filter(table_name=obj.molgenis_table, column_name=obj.molgenis_column)
            .exists()
        )

    def _should_sync_saved_stat_definition(self, obj: StatDefinition, form, change: bool) -> bool:
        if not obj.is_active:
            return False
        if not change:
            return True

        changed_data = set(getattr(form, 'changed_data', []) or [])
        sync_relevant_fields = {'distribution', 'molgenis_table', 'molgenis_column', 'is_active'}
        return bool(changed_data & sync_relevant_fields) or not self._stat_result_exists(obj)

    def _sync_saved_stat_definition(self, request, obj: StatDefinition) -> None:
        from fair_genomes.models import StatResult
        from fair_genomes.services.fair_genomes_service import FairGenomesService

        api_url = getattr(settings, 'FAIR_GENOMES_API_URL', '')
        if not api_url:
            messages.warning(
                request,
                _(
                    'Statistic definition was saved, but aggregation was not synchronised '
                    'because FAIR_GENOMES_API_URL is not configured.'
                ),
            )
            return

        started_at = time.monotonic()
        mark_started(FairGenomesSyncState.SourceType.STATISTICS, source_url=api_url)
        success, error = FairGenomesService().sync_single_stat(
            obj.molgenis_table,
            obj.molgenis_column,
        )
        duration = round(time.monotonic() - started_at, 2)
        summary = stats_report_summary(
            {
                'updated': 1 if success else 0,
                'failed': 0 if success else 1,
                'errors': [] if success else [error],
            }
        )

        if not success:
            mark_failed(
                FairGenomesSyncState.SourceType.STATISTICS,
                source_url=api_url,
                duration_seconds=duration,
                summary=summary,
                error_message=error,
            )
            messages.warning(
                request,
                _(
                    'Statistic definition was saved, but aggregation synchronisation failed: %(error)s'
                )
                % {'error': error},
            )
            return

        mark_success(
            FairGenomesSyncState.SourceType.STATISTICS,
            source_url=api_url,
            duration_seconds=duration,
            summary=summary,
        )
        result = (
            StatResult.objects.using('fair_genomes_db')
            .filter(table_name=obj.molgenis_table, column_name=obj.molgenis_column)
            .first()
        )
        if result and result.distribution:
            messages.success(
                request,
                _('Statistic definition was saved and its aggregation was synchronised.'),
            )
        else:
            messages.warning(
                request,
                _(
                    'Statistic definition was saved and synchronised, but MOLGENIS returned '
                    'no grouped values for this table and column.'
                ),
            )

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        super().save_model(request, obj, form, change)
        if self._should_sync_saved_stat_definition(obj, form, change):
            self._sync_saved_stat_definition(request, obj)

    # All staff can fully manage stat definitions without needing explicit
    # model-level permissions assigned by a superuser.
    def has_module_permission(self, request):  # type: ignore[override]
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_staff

    def has_add_permission(self, request):  # type: ignore[override]
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):  # type: ignore[override]
        return request.user.is_staff

    class Media:
        js = ('js/stat_definition_admin.js',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'full-sync/',
                self.admin_site.admin_view(self.full_sync_view),
                name='fair_genomes_full_sync',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_full_sync_button'] = True
        extra_context['full_sync_url'] = reverse('admin:fair_genomes_full_sync')
        extra_context['sync_states'] = _get_sync_state_context()
        extra_context['rdf_inventory_status'] = _get_rdf_inventory_status()
        return super().changelist_view(request, extra_context=extra_context)

    def change_list_template_or_default(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    @property
    def change_list_template(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    def full_sync_view(self, request):
        """Run RDF metadata synchronisation and GraphQL statistic aggregation."""
        if not request.user.is_staff:
            messages.error(request, _('Only staff users can trigger FAIR Genomes synchronisation.'))
            return redirect('..')

        if request.method == 'POST':
            from fair_genomes.services.fair_genomes_service import FairGenomesService

            try:
                svc = FairGenomesService()
                report = svc.sync()
                _clear_live_rdf_inventory_cache()
                status = report.get('status', 'unknown')
                stats = report.get('stats')
                duration = report.get('duration_seconds', '?')

                summary_parts = [
                    _('Status: %(status)s') % {'status': _sync_report_status_label(status)},
                    _('Duration: %(duration)s s') % {'duration': duration},
                ]
                if stats:
                    summary_parts.append(
                        _('Statistics: %(updated)d updated, %(failed)d failed')
                        % {
                            'updated': stats['updated'],
                            'failed': stats['failed'],
                        }
                    )
                message = _('FAIR Genomes synchronisation completed. %(summary)s') % {
                    'summary': ' | '.join(summary_parts)
                }
                if report.get('error') or status == 'failed':
                    messages.error(request, message)
                elif status == 'partial' or (stats and stats.get('failed')):
                    messages.warning(request, message)
                else:
                    messages.success(request, message)
                if stats and stats['failed']:
                    messages.warning(
                        request,
                        _('%(n)d statistic aggregation(s) failed: %(errors)s')
                        % {
                            'n': stats['failed'],
                            'errors': '; '.join(stats['errors'][:5]),
                        },
                    )
            except Exception as exc:
                logger.exception('FAIR Genomes synchronisation failed')
                messages.error(
                    request,
                    _('FAIR Genomes synchronisation failed: %(error)s') % {'error': str(exc)},
                )

            return redirect('..')

        return render(
            request,
            'admin/fair_genomes/statdefinition/full_sync.html',
            {
                'title': _('Check and Synchronise FAIR Genomes Metadata and Statistics'),
                'sync_states': _get_sync_state_context(),
                'rdf_inventory_status': _get_rdf_inventory_status(),
            },
        )

    @admin.action(description=_('Synchronise selected statistic aggregations now'))
    def sync_selected_stats(self, request, queryset):
        """Re-run the _groupBy aggregation for selected StatDefinitions."""
        from fair_genomes.services.fair_genomes_service import FairGenomesService

        api_url = getattr(settings, 'FAIR_GENOMES_API_URL', '')
        if not api_url:
            messages.warning(request, _('FAIR_GENOMES_API_URL is not configured.'))
            return

        svc = FairGenomesService()
        ok_count = 0
        fail_count = 0
        errors: list[str] = []
        started_at = time.monotonic()
        mark_started(FairGenomesSyncState.SourceType.STATISTICS, source_url=api_url)
        for defn in queryset.filter(is_active=True):
            success, err = svc.sync_single_stat(defn.molgenis_table, defn.molgenis_column)
            if success:
                ok_count += 1
            else:
                fail_count += 1
                errors.append(err)

        summary = stats_report_summary(
            {
                'updated': ok_count,
                'failed': fail_count,
                'errors': errors,
            }
        )
        if fail_count:
            mark_failed(
                FairGenomesSyncState.SourceType.STATISTICS,
                source_url=api_url,
                duration_seconds=round(time.monotonic() - started_at, 2),
                summary=summary,
                error_message='; '.join(errors[:5]),
            )
        else:
            mark_success(
                FairGenomesSyncState.SourceType.STATISTICS,
                source_url=api_url,
                duration_seconds=round(time.monotonic() - started_at, 2),
                summary=summary,
            )

        message_params = {'ok': ok_count, 'fail': fail_count}
        if fail_count:
            messages.warning(
                request,
                _('Synchronised %(ok)d statistic aggregation(s), %(fail)d failed.')
                % message_params,
            )
        else:
            messages.success(
                request,
                _('Synchronised %(ok)d statistic aggregation(s), %(fail)d failed.')
                % message_params,
            )


@admin.register(FairGenomesSyncState)
class FairGenomesSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        'source_type',
        'status',
        'last_checked_at',
        'last_success_at',
        'last_failure_at',
        'duration_seconds',
    )
    readonly_fields = (
        'source_type',
        'source_url',
        'status',
        'last_checked_at',
        'last_success_at',
        'last_failure_at',
        'duration_seconds',
        'summary',
        'error_message',
        'updated_at',
    )
    fields = readonly_fields

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
