"""
Single-process startup script — runs all one-off setup tasks inside one
Django process instead of spawning manage.py 7+ times.

Called by docker/entrypoint.sh before the main server command.
"""

import os
import sys
from pathlib import Path

import django
from django.core.management import call_command
from django.db import connections


def _translations_need_compile(locale_dir: Path) -> bool:
    """Return True if any .po file is missing its .mo or is newer than it."""
    for po in locale_dir.rglob('*.po'):
        mo = po.with_suffix('.mo')
        if not mo.exists() or po.stat().st_mtime > mo.stat().st_mtime:
            return True
    return False


def main() -> None:
    django.setup()

    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')

    # ── Migrations ────────────────────────────────────────────────────────────
    # auth_db: sessions, auth, contenttypes, admin
    call_command('migrate', database='auth_db', interactive=False, verbosity=1)

    # default: ticketing and anything else
    call_command('migrate', interactive=False, verbosity=1)

    # fair_genomes_db: fair_genomes app
    call_command('migrate', database='fair_genomes_db', interactive=False, verbosity=1)

    # Repair drifted fair_genomes_db migration state where 0001 is marked applied
    # but core tables are missing (legacy schema leftovers, manual DB changes).
    fg_tables = connections['fair_genomes_db'].introspection.table_names()
    if 'fair_genomes_contact_point' not in fg_tables:
        print(
            'fair_genomes_db migration drift detected (missing fair_genomes_contact_point). '
            'Repairing migration state...',
            flush=True,
        )
        call_command(
            'migrate', 'fair_genomes', 'zero',
            database='fair_genomes_db', fake=True, interactive=False,
        )
        call_command('migrate', 'fair_genomes', database='fair_genomes_db', interactive=False)

    # metadata_db: warehouse app
    call_command('migrate', database='metadata_db', interactive=False, verbosity=1)

    # ── Seed mock data ────────────────────────────────────────────────────────
    if os.environ.get('MOCK_FAIR_GENOMES', 'False') == 'True':
        print('MOCK_FAIR_GENOMES=True — seeding fair_genomes_db with mock data...', flush=True)
        call_command('seed_fair_genomes_mock')

    # ── Translations ──────────────────────────────────────────────────────────
    locale_dir = Path(__file__).resolve().parent.parent / 'locale'
    if _translations_need_compile(locale_dir):
        print('Compiling translations...', flush=True)
        call_command('compilemessages', locale=['cs', 'en'], verbosity=0)
    else:
        print('Translations up to date, skipping compilemessages.', flush=True)

    # ── Static files (skip in dev — runserver serves them directly) ───────────
    if settings_module != 'catalogue.settings.dev':
        call_command('collectstatic', interactive=False, verbosity=0)


if __name__ == '__main__':
    main()
