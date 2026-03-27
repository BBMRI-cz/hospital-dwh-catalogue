"""
Management command to sync Fair Genomes data from a FAIR Data Point RDF endpoint.

The endpoint URL is read from the FAIR_GENOMES_RDF_URL environment variable.
Run with --verbosity 0 to suppress the detailed report and only see errors.
"""

import logging

from django.core.management.base import BaseCommand

from fair_genomes.services import FairGenomesAPIException, FairGenomesService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync Fair Genomes catalogue data from a FAIR Data Point RDF endpoint'

    def handle(self, *args, **options):
        try:
            with FairGenomesService() as service:
                report = service.sync()
        except FairGenomesAPIException as exc:
            self.stderr.write(self.style.ERROR(f'Sync failed: {exc}'))
            return

        status = report.get('status', 'unknown')

        if status == 'skipped':
            self.stdout.write(self.style.WARNING(f"Sync skipped: {report.get('reason')}"))
            return

        # ── Summary header ────────────────────────────────────────────────────
        style_fn = self.style.SUCCESS if status == 'complete' else self.style.WARNING
        self.stdout.write(style_fn(f'Sync status: {status.upper()}'))
        self.stdout.write(f"Source: {report.get('rdf_url')}")
        self.stdout.write('')

        # ── Fetched ───────────────────────────────────────────────────────────
        fetched = report.get('fetched', {})
        self.stdout.write('FETCHED FROM RDF:')
        for entity in ('agents', 'catalogs', 'datasets'):
            names = fetched.get(entity, [])
            self.stdout.write(f'  {entity.capitalize():<10} ({len(names)}): {names}')
        self.stdout.write('')

        # ── Saved ─────────────────────────────────────────────────────────────
        saved = report.get('saved', {})
        self.stdout.write('SAVED:')
        for entity in ('agents', 'catalogs'):
            created = saved.get(entity, {}).get('created', [])
            updated = saved.get(entity, {}).get('updated', [])
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'  {entity.capitalize()} created: {created}')
                )
            if updated:
                self.stdout.write(f'  {entity.capitalize()} updated: {updated}')
            if not created and not updated:
                self.stdout.write(f'  {entity.capitalize()}: nothing saved')
        self.stdout.write('')

        # ── Partial saves ─────────────────────────────────────────────────────
        partial_saves = report.get('partial_saves', {})
        if any(v for v in partial_saves.values()):
            self.stdout.write('PARTIAL SAVES (fields missing from RDF, filled with defaults):')
            for entity, items in partial_saves.items():
                if isinstance(items, dict):
                    for item_name, notes in items.items():
                        self.stdout.write(
                            self.style.WARNING(f"  {entity.capitalize()} '{item_name}':")
                        )
                        for note in notes:
                            self.stdout.write(f'    - {note}')
            self.stdout.write('')

        # ── Not saved — datasets ──────────────────────────────────────────────
        not_saved_datasets = report.get('not_saved', {}).get('datasets', [])
        if not_saved_datasets:
            self.stdout.write(
                self.style.WARNING(
                    f'NOT SAVED — Datasets ({len(not_saved_datasets)} total, '
                    'missing required fields):'
                )
            )
            for ds in not_saved_datasets:
                self.stdout.write(self.style.WARNING(f"  '{ds['name']}': {ds['reason']}"))
                for f in ds.get('missing_required', []):
                    self.stdout.write(f'    Missing required: {f}')
                self.stdout.write(
                    f"    Available in RDF:  {', '.join(ds.get('available_fields', []))}"
                )
                rdf_not_in_model = ds.get('rdf_fields_not_in_model', {})
                if rdf_not_in_model:
                    for field, value in rdf_not_in_model.items():
                        self.stdout.write(f'    In RDF but not in model: {field} = {value!r}')
            self.stdout.write('')

        # ── RDF fields with no model equivalent ───────────────────────────────
        rdf_not_in_model = report.get('rdf_fields_not_in_model', {})
        if rdf_not_in_model:
            self.stdout.write('RDF FIELDS WITH NO MODEL EQUIVALENT:')
            for entity, fields in rdf_not_in_model.items():
                self.stdout.write(f'  {entity}:')
                for f in fields:
                    self.stdout.write(f'    - {f}')
            self.stdout.write('')

        # ── Model fields absent from RDF ──────────────────────────────────────
        model_not_in_rdf = report.get('model_fields_not_in_rdf', {})
        if model_not_in_rdf:
            self.stdout.write(
                'MODEL FIELDS NOT IN RDF '
                '(must be filled manually or via a second sync phase):'
            )
            for entity, fields in model_not_in_rdf.items():
                self.stdout.write(f'  {entity}: {", ".join(fields)}')

