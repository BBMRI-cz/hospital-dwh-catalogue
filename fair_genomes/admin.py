"""
Fair Genomes Admin Configuration
"""

import json
import logging

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import Dataset, Distribution, StatDefinition

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
        self.fields['distribution'] = forms.ChoiceField(
            choices=dist_choices,
            label=_('Distribution'),
            help_text=_('DCAT Distribution whose detail page should show this chart.'),
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
        return super().changelist_view(request, extra_context=extra_context)

    def change_list_template_or_default(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    @property
    def change_list_template(self):
        return 'admin/fair_genomes/statdefinition/change_list.html'

    def full_sync_view(self, request):
        """Full RDF + GraphQL resync, accessible via admin button."""
        if not request.user.is_staff:
            messages.error(request, _('Only staff users can trigger a full sync.'))
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
                        f'Stats: {stats["updated"]} updated, {stats["failed"]} failed'
                    )
                messages.success(
                    request,
                    _('Full sync completed. %(summary)s') % {'summary': ' | '.join(summary_parts)},
                )
                if stats and stats['failed']:
                    messages.warning(
                        request,
                        _('%(n)d stat aggregation(s) failed: %(errors)s')
                        % {
                            'n': stats['failed'],
                            'errors': '; '.join(stats['errors'][:5]),
                        },
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
            success, _err = svc.sync_single_stat(defn.molgenis_table, defn.molgenis_column)
            if success:
                ok_count += 1
            else:
                fail_count += 1

        messages.success(
            request,
            _('Synced %(ok)d stats, %(fail)d failed.') % {'ok': ok_count, 'fail': fail_count},
        )
