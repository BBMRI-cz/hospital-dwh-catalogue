"""Shared helpers for docker startup orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

ENV_SUPERUSER_SENTINEL_EMAIL = 'env-managed-superuser@localhost'


def env_superuser_credentials(environ: Mapping[str, str]) -> tuple[str, str] | None:
    username = environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
    password = environ.get('DJANGO_SUPERUSER_PASSWORD', '').strip()
    if not username or not password:
        return None
    return username, password


def translations_need_compile(locale_dir: Path) -> bool:
    """Return True if any .po file is missing its .mo or is newer than it."""
    for po in locale_dir.rglob('*.po'):
        mo = po.with_suffix('.mo')
        if not mo.exists() or po.stat().st_mtime > mo.stat().st_mtime:
            return True
    return False


def tailwind_build_command(base_dir: Path) -> list[str]:
    return [
        'tailwindcss',
        '-c',
        str(base_dir / 'tailwind.config.cjs'),
        '-i',
        str(base_dir / 'frontend' / 'static' / 'css' / 'tailwind.input.css'),
        '-o',
        str(base_dir / 'frontend' / 'static' / 'css' / 'tailwind.css'),
        '--minify',
    ]


def normalize_table_identifier(table_name: str) -> str:
    """Normalize Django/Postgres table identifiers for existence checks.

    Django models use ``metadata"."lm_contact_point`` to make PostgreSQL emit
    ``"metadata"."lm_contact_point"``.  For direct catalog checks this needs to
    become the regular schema-qualified form ``metadata.lm_contact_point``.
    """
    return table_name.strip().replace('"."', '.').replace('"', '').strip('.')


def table_is_missing(table_names: list[str], table_name: str) -> bool:
    normalized_table_name = normalize_table_identifier(table_name)
    normalized_table_names = {normalize_table_identifier(candidate) for candidate in table_names}

    if normalized_table_name in normalized_table_names:
        return False

    unqualified = normalized_table_name.split('.')[-1]
    for candidate in normalized_table_names:
        if candidate == unqualified:
            return False
        if candidate.endswith(f'.{unqualified}'):
            return False
    return True


def table_exists(connection: Any, table_name: str) -> bool:
    """Return whether a table exists, including PostgreSQL schema-qualified names."""
    if connection.vendor == 'postgresql':
        return _postgres_table_exists(connection, table_name)

    return not table_is_missing(connection.introspection.table_names(), table_name)


def _postgres_table_exists(connection: Any, table_name: str) -> bool:
    normalized_table_name = normalize_table_identifier(table_name)
    parts = normalized_table_name.split('.', 1)

    with connection.cursor() as cursor:
        if len(parts) == 2:
            schema_name, relation_name = parts
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_name = %s
                )
                """,
                [schema_name, relation_name],
            )
        else:
            cursor.execute('SELECT to_regclass(%s) IS NOT NULL', [normalized_table_name])

        row = cursor.fetchone()

    return bool(row and row[0])


def should_seed_mock_fair_genomes(environ: Mapping[str, str]) -> bool:
    return environ.get('MOCK_FAIR_GENOMES', 'False') == 'True'


def should_seed_mock_warehouse_metadata(environ: Mapping[str, str]) -> bool:
    return environ.get('MOCK_WAREHOUSE_METADATA', 'False') == 'True'


def should_collectstatic(settings_module: str) -> bool:
    return settings_module != 'catalogue.settings.dev'
