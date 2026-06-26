"""
Single-process startup script - runs all one-off setup tasks inside one
Django process instead of spawning manage.py 7+ times.

Called by docker/entrypoint.sh before the main server command.
"""

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from startup_tasks import (
    ENV_SUPERUSER_SENTINEL_EMAIL,
    env_superuser_credentials,
    should_collectstatic,
    should_seed_mock_fair_genomes,
    should_seed_mock_warehouse_metadata,
    table_exists,
    tailwind_build_command,
    translations_need_compile,
)

import django
from django.core.management import call_command
from django.db import connections

KNOWN_INITIAL_MIGRATION_TABLES = {
    'fair_genomes': (
        'fair_genomes_agent',
        'fair_genomes_contact_point',
        'fair_genomes_sync_state',
        'fair_genomes_catalog',
        'fair_genomes_dataset',
        'fair_genomes_distribution',
        'fair_genomes_stat_result',
        'fair_genomes_stat_definition',
    ),
    'warehouse': (
        'metadata.lm_agent',
        'metadata.lm_contact_point',
        'metadata.lm_catalog',
        'metadata.lm_dataset',
        'metadata.lm_distribution',
        'metadata.lm_table',
        'metadata.lm_column',
    ),
}


def _ensure_env_superuser() -> None:
    """
    Create or update the env-managed superuser from DJANGO_SUPERUSER_USERNAME
    and DJANGO_SUPERUSER_PASSWORD environment variables.

    Behaviour on every startup:
    - If either env var is missing/blank, skip silently.
    - Any existing env-managed user (sentinel email) with a *different* username
      is deleted first - this handles username rotation in .env.
    - The target user is then created or claimed:
        * Newly created  -> fully configured as superuser with sentinel email.
        * Exists, sentinel email present -> re-stamp (LDAP may have overwritten
          it via AUTH_LDAP_ALWAYS_UPDATE_USER=True) and sync password + flags.
        * Exists, no sentinel, but is_superuser=True and has a usable password
          -> treat as a previously env-managed user whose sentinel was lost to an
          LDAP sync; re-claim and sync password + flags.
        * Exists, no sentinel, not a local-password superuser -> genuine AD/LDAP
          user that happens to share the username; leave untouched and warn.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import User

    credentials = env_superuser_credentials(os.environ)
    if credentials is None:
        print(
            'DJANGO_SUPERUSER_USERNAME/PASSWORD not set - skipping env superuser setup.',
            flush=True,
        )
        return
    username, password = credentials

    UserModel = get_user_model()

    # -- Remove stale env-managed user (username changed in .env) -------------
    deleted_count, _ = (
        UserModel.objects.using('auth_db')
        .filter(email=ENV_SUPERUSER_SENTINEL_EMAIL)
        .exclude(username=username)
        .delete()
    )
    if deleted_count:
        print(f'Env superuser: deleted {deleted_count} stale env-managed user(s).', flush=True)

    # -- Create or update target user ------------------------------------------
    result = UserModel.objects.using('auth_db').get_or_create(
        username=username,
        defaults={
            'email': ENV_SUPERUSER_SENTINEL_EMAIL,
            'is_staff': True,
            'is_superuser': True,
        },
    )
    user: User = result[0]  # type: ignore[assignment]
    created: bool = result[1]

    if created:
        user.set_password(password)
        user.save(using='auth_db')
        print(f"Env superuser: created '{username}'.", flush=True)
        return

    # User already existed - decide whether to claim/re-claim it.
    has_sentinel = user.email == ENV_SUPERUSER_SENTINEL_EMAIL
    is_local_superuser = user.is_superuser and user.has_usable_password()

    if not has_sentinel and not is_local_superuser:
        # Pure LDAP user (no usable local password, no sentinel): leave alone.
        print(
            f"Env superuser: '{username}' exists as an LDAP-only user - skipping to avoid conflict. "
            f'Choose a username that does not exist in Active Directory.',
            flush=True,
        )
        return

    # Either sentinel is present (normal case or re-stamp after LDAP overwrite)
    # or it's a local-password superuser we previously owned: re-claim.
    user.email = ENV_SUPERUSER_SENTINEL_EMAIL
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save(using='auth_db')

    action = 'updated (re-stamped sentinel)' if not has_sentinel else 'updated'
    print(f"Env superuser: '{username}' {action}.", flush=True)


def _build_tailwind_css(base_dir: Path) -> None:
    """Build Tailwind CSS from source using the standalone CLI.

    Runs on every startup so the compiled CSS stays in sync with template
    changes when the source tree is volume-mounted in dev.  Skips gracefully
    when the ``tailwindcss`` binary is not available (e.g. unit-test runners
    that execute this script outside the container).
    """
    if not shutil.which('tailwindcss'):
        print('tailwindcss binary not found - skipping CSS build.', flush=True)
        return

    result = subprocess.run(
        tailwind_build_command(base_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f'Tailwind CSS build failed:\n{result.stderr}', flush=True)
    else:
        print('Tailwind CSS built successfully.', flush=True)


def _migrate_database(database: str) -> None:
    kwargs = {'interactive': False, 'verbosity': 1}
    if database != 'default':
        kwargs['database'] = database
    call_command('migrate', **kwargs)


def _migrate_app(database: str, app_label: str, *targets: str, fake: bool = False) -> None:
    kwargs = {'interactive': False}
    if fake:
        kwargs['fake'] = True
    if database != 'default':
        kwargs['database'] = database
    call_command('migrate', app_label, *targets, **kwargs)


def _migration_is_recorded(database: str, app_label: str, migration_name: str) -> bool:
    connection = connections[database]
    if not table_exists(connection, 'django_migrations'):
        return False

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM django_migrations
            WHERE app = %s
              AND name = %s
            LIMIT 1
            """,
            [app_label, migration_name],
        )
        return cursor.fetchone() is not None


def _fake_initial_migration_if_schema_exists(
    *,
    database: str,
    app_label: str,
    migration_name: str = '0001_initial',
    table_names: Sequence[str],
) -> None:
    if _migration_is_recorded(database, app_label, migration_name):
        return

    connection = connections[database]
    existing_tables = [table_name for table_name in table_names if table_exists(connection, table_name)]
    if not existing_tables:
        return

    if len(existing_tables) != len(table_names):
        missing_tables = sorted(set(table_names) - set(existing_tables))
        raise RuntimeError(
            f'{database} contains a partial {app_label} initial schema without a '
            f'{migration_name} migration record. Existing tables: {sorted(existing_tables)}. '
            f'Missing tables: {missing_tables}. Repair the schema before deploying.'
        )

    print(
        f'{database} has all {app_label} initial tables but no {migration_name} '
        'migration record. Marking the migration as applied.',
        flush=True,
    )
    _migrate_app(database, app_label, migration_name, fake=True)


def _repair_missing_app_table(
    *,
    database: str,
    app_label: str,
    sentinel_table: str,
) -> None:
    if table_exists(connections[database], sentinel_table):
        return

    print(
        f'{database} migration drift detected (missing {sentinel_table}). '
        'Repairing migration state...',
        flush=True,
    )
    _migrate_app(database, app_label, 'zero', fake=True)
    _migrate_app(database, app_label)


def _seed_mock_data_if_needed() -> None:
    if not should_seed_mock_fair_genomes(os.environ):
        pass
    else:
        print('MOCK_FAIR_GENOMES=True - seeding fair_genomes_db with mock data...', flush=True)
        call_command('seed_fair_genomes_mock')

    if should_seed_mock_warehouse_metadata(os.environ):
        print('MOCK_WAREHOUSE_METADATA=True - seeding metadata_db with mock data...', flush=True)
        call_command('seed_warehouse_mock')


def _compile_translations_if_needed(base_dir: Path) -> None:
    locale_dir = base_dir / 'locale'
    if translations_need_compile(locale_dir):
        print('Compiling translations...', flush=True)
        call_command('compilemessages', locale=['cs', 'en'], verbosity=0)
    else:
        print('Translations up to date, skipping compilemessages.', flush=True)


def main() -> None:
    django.setup()

    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    base_dir = Path(__file__).resolve().parent.parent

    # -- Migrations ------------------------------------------------------------
    _migrate_database('auth_db')
    _ensure_env_superuser()

    _migrate_database('default')
    _repair_missing_app_table(
        database='default',
        app_label='ticketing',
        sentinel_table='ticketing_ticket_request',
    )

    _fake_initial_migration_if_schema_exists(
        database='fair_genomes_db',
        app_label='fair_genomes',
        table_names=KNOWN_INITIAL_MIGRATION_TABLES['fair_genomes'],
    )
    _migrate_database('fair_genomes_db')
    _repair_missing_app_table(
        database='fair_genomes_db',
        app_label='fair_genomes',
        sentinel_table='fair_genomes_contact_point',
    )

    _fake_initial_migration_if_schema_exists(
        database='metadata_db',
        app_label='warehouse',
        table_names=KNOWN_INITIAL_MIGRATION_TABLES['warehouse'],
    )
    _migrate_database('metadata_db')
    _repair_missing_app_table(
        database='metadata_db',
        app_label='warehouse',
        sentinel_table='metadata.lm_contact_point',
    )

    # -- Seed mock data --------------------------------------------------------
    _seed_mock_data_if_needed()

    # -- Tailwind CSS ----------------------------------------------------------
    _build_tailwind_css(base_dir)

    # -- Translations ----------------------------------------------------------
    _compile_translations_if_needed(base_dir)

    # -- Static files (skip in dev - runserver serves them directly) -----------
    if should_collectstatic(settings_module):
        call_command('collectstatic', clear=True, interactive=False, verbosity=0)


if __name__ == '__main__':
    main()
