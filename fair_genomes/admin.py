"""
FAIR Genomes Admin Configuration
"""

import logging
import time

from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import FairGenomesSyncState, StatDefinition
from fair_genomes.services.admin_forms import StatDefinitionForm
from fair_genomes.services.admin_support import (
    clear_rdf_source_inventory_cache,
    get_rdf_inventory_status,
    get_sync_state_context,
    sync_report_status_label,
)
from fair_genomes.services.sync_state import (
    mark_failed,
    mark_started,
    mark_success,
    stats_report_summary,
)

logger = logging.getLogger(__name__)


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
        extra_context['sync_states'] = get_sync_state_context()
        extra_context['rdf_inventory_status'] = get_rdf_inventory_status()
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
                clear_rdf_source_inventory_cache()
                status = report.get('status', 'unknown')
                stats = report.get('stats')
                duration = report.get('duration_seconds', '?')

                summary_parts = [
                    _('Status: %(status)s') % {'status': sync_report_status_label(status)},
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
                'sync_states': get_sync_state_context(),
                'rdf_inventory_status': get_rdf_inventory_status(),
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
