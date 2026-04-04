"""
Fair Genomes Admin Configuration
"""

import logging

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import Distribution, StatDefinition, StatResult

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_KEY = 'fg_molgenis_schema'
_SCHEMA_CACHE_TTL = 300  # 5 minutes


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


class StatDefinitionForm(forms.ModelForm):
    """
    ModelForm for StatDefinition with dynamic choices from MOLGENIS
    introspection.  Falls back to free-text input if MOLGENIS is unreachable.
    """

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
            # MOLGENIS unreachable — keep plain text inputs.
            self._molgenis_schema = None


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'dataset_name')
    search_fields = ('name', 'title')
    ordering = ('name',)


@admin.register(StatDefinition)
class StatDefinitionAdmin(admin.ModelAdmin):
    form = StatDefinitionForm
    list_display = (
        'distribution',
        'molgenis_table',
        'molgenis_column',
        'display_label',
        'is_active',
        'sort_order',
    )
    list_filter = ('is_active', 'distribution')
    list_editable = ('is_active', 'sort_order')
    ordering = ('distribution', 'sort_order')
    actions = ['sync_selected_stats']
    list_per_page = 50

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
        return super().changelist_view(request, extra_context=extra_context)

    def change_list_template_or_default(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    @property
    def change_list_template(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    def full_sync_view(self, request):
        """Full RDF + GraphQL resync, accessible via admin button."""
        if not request.user.is_superuser:
            messages.error(request, _('Only superusers can trigger a full sync.'))
            return redirect('..')

        if request.method == 'POST':
            from fair_genomes.services.fair_genomes_service import FairGenomesService

            try:
                svc = FairGenomesService()
                report = svc.sync()
                status = report.get('status', 'unknown')
                stats = report.get('stats')
                duration = report.get('duration_seconds', '?')

                summary_parts = [f'Status: {status}', f'Duration: {duration}s']
                if stats:
                    summary_parts.append(
                        f'Stats: {stats["updated"]} updated, ' f'{stats["failed"]} failed'
                    )
                messages.success(
                    request,
                    _('Full sync completed. %(summary)s') % {'summary': ' | '.join(summary_parts)},
                )
            except Exception as exc:
                logger.exception('Full sync failed')
                messages.error(
                    request,
                    _('Full sync failed: %(error)s') % {'error': str(exc)},
                )

            return redirect('..')

        return render(
            request,
            'admin/fair_genomes/statdefinition/full_sync.html',
            {'title': _('Full Sync (RDF + Stats)')},
        )

    @admin.action(description=_('Sync selected stat aggregations now'))
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
        for defn in queryset.filter(is_active=True):
            success, err = svc.sync_single_stat(defn.molgenis_table, defn.molgenis_column)
            if success:
                ok_count += 1
            else:
                fail_count += 1

        messages.success(
            request,
            _('Synced %(ok)d stats, %(fail)d failed.') % {'ok': ok_count, 'fail': fail_count},
        )


@admin.register(StatResult)
class StatResultAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'column_name', 'last_synced')
    list_filter = ('table_name', 'column_name')
    search_fields = ('table_name', 'column_name')
    readonly_fields = ('distribution', 'last_synced')
    ordering = ('table_name', 'column_name')
