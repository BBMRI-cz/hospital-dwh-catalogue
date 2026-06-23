"""Shared helpers for docker startup orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

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


def table_is_missing(table_names: list[str], table_name: str) -> bool:
    return table_name not in table_names


def should_seed_mock_fair_genomes(environ: Mapping[str, str]) -> bool:
    return environ.get('MOCK_FAIR_GENOMES', 'False') == 'True'


def should_seed_mock_warehouse_metadata(environ: Mapping[str, str]) -> bool:
    return environ.get('MOCK_WAREHOUSE_METADATA', 'False') == 'True'


def should_collectstatic(settings_module: str) -> bool:
    return settings_module != 'catalogue.settings.dev'
