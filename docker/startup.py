"""
Single-process startup script — runs all one-off setup tasks inside one
Django process instead of spawning manage.py 7+ times.

Called by docker/entrypoint.sh before the main server command.
"""

import logging
import os
from pathlib import Path

import django
from django.core.management import call_command
from django.db import connections

logger = logging.getLogger(__name__)

# Sentinel email that marks env-managed superuser accounts.
# This allows the startup script to track which user it owns across restarts,
# even if LDAP (AUTH_LDAP_ALWAYS_UPDATE_USER) overwrites the email field.
_ENV_SUPERUSER_SENTINEL_EMAIL = '__env_managed__@localhost'


def _ensure_env_superuser() -> None:
    """
    Create or update the env-managed superuser from DJANGO_SUPERUSER_USERNAME
    and DJANGO_SUPERUSER_PASSWORD environment variables.

    Behaviour on every startup:
    - If either env var is missing/blank, skip silently.
    - Any existing env-managed user (sentinel email) with a *different* username
      is deleted first — this handles username rotation in .env.
    - The target user is then created or claimed:
        * Newly created  → fully configured as superuser with sentinel email.
        * Exists, sentinel email present → re-stamp (LDAP may have overwritten
          it via AUTH_LDAP_ALWAYS_UPDATE_USER=True) and sync password + flags.
        * Exists, no sentinel, but is_superuser=True and has a usable password
          → treat as a previously env-managed user whose sentinel was lost to an
          LDAP sync; re-claim and sync password + flags.
        * Exists, no sentinel, not a local-password superuser → genuine AD/LDAP
          user that happens to share the username; leave untouched and warn.
    """
    from django.contrib.auth import get_user_model

    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '').strip()

    if not username or not password:
        print(
            'DJANGO_SUPERUSER_USERNAME/PASSWORD not set — skipping env superuser bootstrap.',
            flush=True,
        )
        return

    User = get_user_model()

    # ── Remove stale env-managed user (username changed in .env) ─────────────
    deleted_count, _ = (
        User.objects.using('auth_db')
        .filter(email=_ENV_SUPERUSER_SENTINEL_EMAIL)
        .exclude(username=username)
        .delete()
    )
    if deleted_count:
        print(f'Env superuser: deleted {deleted_count} stale env-managed user(s).', flush=True)

    # ── Create or update target user ──────────────────────────────────────────
    user, created = User.objects.using('auth_db').get_or_create(
        username=username,
        defaults={
            'email': _ENV_SUPERUSER_SENTINEL_EMAIL,
            'is_staff': True,
            'is_superuser': True,
        },
    )

    if created:
        user.set_password(password)
        user.save(using='auth_db')
        print(f"Env superuser: created '{username}'.", flush=True)
        return

    # User already existed — decide whether to claim/re-claim it.
    has_sentinel = user.email == _ENV_SUPERUSER_SENTINEL_EMAIL
    is_local_superuser = user.is_superuser and user.has_usable_password()

    if not has_sentinel and not is_local_superuser:
        # Pure LDAP user (no usable local password, no sentinel): leave alone.
        print(
            f"Env superuser: '{username}' exists as an LDAP-only user — skipping to avoid conflict. "
            f'Choose a username that does not exist in Active Directory.',
            flush=True,
        )
        return

    # Either sentinel is present (normal case or re-stamp after LDAP overwrite)
    # or it's a local-password superuser we previously owned: re-claim.
    user.email = _ENV_SUPERUSER_SENTINEL_EMAIL
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save(using='auth_db')

    action = 'updated (re-stamped sentinel)' if not has_sentinel else 'updated'
    print(f"Env superuser: '{username}' {action}.", flush=True)


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

    # ── Env-managed superuser ─────────────────────────────────────────────────
    _ensure_env_superuser()

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
            'migrate',
            'fair_genomes',
            'zero',
            database='fair_genomes_db',
            fake=True,
            interactive=False,
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
