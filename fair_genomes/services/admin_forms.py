"""Admin form classes for FAIR Genomes configuration."""

import json

from django import forms
from django.utils.translation import gettext_lazy as _

from fair_genomes.models import Dataset, Distribution, StatDefinition
from fair_genomes.services.admin_support import get_molgenis_schema, get_rdf_inventory_status


class StatDefinitionForm(forms.ModelForm):
    """
    Dynamic StatDefinition form.

    MOLGENIS table/column choices come from schema introspection when available.
    Distribution choices come from locally synchronised FAIR Genomes metadata.
    The RDF source inventory check prevents new statistic definitions from
    being saved against stale local metadata.
    """

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
        distributions = self._configure_dataset_and_distribution_fields()
        self._configure_molgenis_fields()
        self._set_initial_dataset(distributions)
        self._apply_field_order()

    def _configure_dataset_and_distribution_fields(self) -> list[Distribution]:
        datasets = Dataset.objects.using('fair_genomes_db').order_by('title')
        self.fields['dataset'].choices = [('', '---------')] + [
            (ds.name, ds.title or ds.name) for ds in datasets
        ]

        distributions = list(
            Distribution.objects.using('fair_genomes_db')
            .select_related('dataset_name')
            .order_by('dataset_name__title', 'title')
        )
        distribution_choices = [('', '---------')] + [
            (
                distribution.name,
                (
                    f'{distribution.dataset_name.title or distribution.dataset_name_id} '
                    f'-> {distribution.title or distribution.name}'
                ),
            )
            for distribution in distributions
        ]
        distribution_dataset_map = {
            distribution.name: distribution.dataset_name_id for distribution in distributions
        }
        self.fields['distribution'] = forms.ChoiceField(
            choices=distribution_choices,
            label=_('Distribution'),
            help_text=self._distribution_help_text(),
            widget=forms.Select(attrs={'data-dist-map': json.dumps(distribution_dataset_map)}),
        )
        return distributions

    def _distribution_help_text(self) -> str:
        base_help = _('DCAT Distribution whose detail page should show this chart.')
        rdf_status = get_rdf_inventory_status()
        if rdf_status['status'] == 'available' and rdf_status['missing_local_distribution_count']:
            return _(
                'DCAT Distribution whose detail page should show this chart. '
                'The RDF source contains %(count)d distribution(s) that are not yet available '
                'in the local catalogue; run "Check and synchronise FAIR Genomes metadata" '
                'before configuring charts for them.'
            ) % {'count': rdf_status['missing_local_distribution_count']}
        if rdf_status['status'] == 'unavailable':
            return _(
                'DCAT Distribution whose detail page should show this chart. '
                'The RDF source could not be checked; showing locally synchronised values.'
            )
        if rdf_status['status'] == 'not_configured':
            return _(
                'DCAT Distribution whose detail page should show this chart. '
                'FAIR_GENOMES_RDF_URL is not configured; showing locally synchronised values.'
            )
        return base_help

    def _configure_molgenis_fields(self) -> None:
        schema = get_molgenis_schema()
        if schema:
            self._configure_live_molgenis_fields(schema)
        else:
            self._configure_fallback_molgenis_fields()

    def _configure_live_molgenis_fields(self, schema: dict[str, list[str]]) -> None:
        table_choices = [('', '---------')] + [(table, table) for table in sorted(schema.keys())]
        self.fields['molgenis_table'] = forms.ChoiceField(
            choices=table_choices,
            label=_('MOLGENIS table'),
            help_text=_('MOLGENIS table name, e.g. "sequencing"'),
        )

        column_choices: list[tuple[str, str]] = [('', '---------')]
        for table_name, columns in sorted(schema.items()):
            for column in columns:
                column_choices.append((column, f'{table_name} -> {column}'))
        self.fields['molgenis_column'] = forms.ChoiceField(
            choices=column_choices,
            label=_('MOLGENIS column'),
            help_text=_('Column name within the table.'),
        )
        self._molgenis_schema = schema

    def _configure_fallback_molgenis_fields(self) -> None:
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

        self.fields['molgenis_table'] = forms.ChoiceField(
            choices=[('', '---------')] + [(table, table) for table in existing_tables],
            label=_('MOLGENIS table'),
            help_text=_('MOLGENIS is currently unreachable. Showing known values.'),
            required=False,
        )
        self.fields['molgenis_column'] = forms.ChoiceField(
            choices=[('', '---------')]
            + [(column, f'{table} -> {column}') for table, column in existing_pairs],
            label=_('MOLGENIS column'),
            help_text=_('MOLGENIS is currently unreachable. Showing known values.'),
            required=False,
        )
        self._molgenis_schema = None

    def _set_initial_dataset(self, distributions: list[Distribution]) -> None:
        if not self.instance or not self.instance.pk:
            return

        self.fields['distribution'].initial = self.instance.distribution_id
        current_distribution = next(
            (
                distribution
                for distribution in distributions
                if distribution.name == self.instance.distribution_id
            ),
            None,
        )
        if current_distribution:
            self.fields['dataset'].initial = current_distribution.dataset_name_id

    def _apply_field_order(self) -> None:
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
            (field_name, self.fields[field_name])
            for field_name in desired_order
            if field_name in self.fields
        )

    def clean_distribution(self):
        name = self.cleaned_data.get('distribution')
        if not name:
            raise forms.ValidationError(_('This field is required.'))
        try:
            return Distribution.objects.using('fair_genomes_db').get(pk=name)
        except Distribution.DoesNotExist:
            raise forms.ValidationError(_('Select a valid choice. That choice is not available.'))

    def clean(self):
        cleaned_data = super().clean()
        rdf_status = get_rdf_inventory_status()
        if rdf_status['status'] != 'available':
            return cleaned_data

        if (
            rdf_status['missing_local_distribution_count']
            or rdf_status['stale_local_distribution_count']
        ):
            raise forms.ValidationError(
                _(
                    'FAIR Genomes RDF metadata is not synchronised with the local catalogue. '
                    'Run "Check and synchronise FAIR Genomes metadata" before configuring statistics.'
                )
            )

        return cleaned_data
