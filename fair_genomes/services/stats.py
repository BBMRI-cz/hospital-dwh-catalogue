"""Stats-sync and schema-introspection helpers for FAIR Genomes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests

from fair_genomes.models import StatDefinition, StatResult
from fair_genomes.services.client import build_graphql_headers, post_graphql_json

logger = logging.getLogger(__name__)


def sync_stats(
    *,
    graphql_url: str,
    api_token: str | None,
    timeout: tuple[int, int] | int,
) -> dict:
    definitions = (
        StatDefinition.objects.using('fair_genomes_db')
        .filter(is_active=True)
        .select_related('distribution')
    )
    updated = 0
    failed = 0
    errors: list[str] = []

    for definition in definitions:
        ok, error = sync_single_stat(
            graphql_url=graphql_url,
            api_token=api_token,
            timeout=timeout,
            table=definition.molgenis_table,
            column=definition.molgenis_column,
        )
        if ok:
            updated += 1
        else:
            failed += 1
            errors.append(error)

    return {'updated': updated, 'failed': failed, 'errors': errors}


def sync_single_stat(
    *,
    graphql_url: str,
    api_token: str | None,
    timeout: tuple[int, int] | int,
    table: str,
    column: str,
) -> tuple[bool, str]:
    table = table.strip()
    column = column.strip()
    if not table or not column:
        return False, 'MOLGENIS table and column are required.'

    table_cap = table[0].upper() + table[1:]
    queries = (
        f'{{ {table_cap}_groupBy {{ count {column} {{ value }} }} }}',
        f'{{ {table_cap}_groupBy {{ count {column} }} }}',
    )
    data = None
    headers = build_graphql_headers(api_token)

    for attempt, query in enumerate(queries):
        is_last = attempt == len(queries) - 1
        try:
            response = requests.post(
                graphql_url,
                json={'query': query},
                headers=headers,
                timeout=timeout,
            )
            if response.status_code == 400 and not is_last:
                continue
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            message = f'{table}.{column}: {exc}'
            logger.warning('Stat sync failed: %s', message)
            return False, message

        if 'errors' not in data:
            break

    if data and 'errors' in data:
        message = f'{table}.{column}: GraphQL errors {data["errors"]}'
        logger.warning('Stat sync GraphQL error: %s', message)
        return False, message

    rows = data.get('data', {}).get(f'{table_cap}_groupBy', []) or []
    distribution: dict[str, int] = {}
    for row in rows:
        count = row.get('count', 0)
        column_value = row.get(column)
        if isinstance(column_value, dict):
            value = (
                column_value.get('value')
                or column_value.get('name')
                or column_value.get('label')
                or ''
            )
        elif column_value is not None:
            value = str(column_value)
        else:
            value = ''
        if value:
            distribution[value] = count

    StatResult.objects.using('fair_genomes_db').update_or_create(
        table_name=table,
        column_name=column,
        defaults={
            'distribution': distribution,
            'last_synced': datetime.now(tz=UTC),
        },
    )
    return True, ''


def introspect_molgenis_schema(
    *,
    graphql_url: str,
    api_token: str | None,
    timeout: tuple[int, int] | int,
) -> dict[str, list[str]]:
    if not graphql_url:
        return {}

    try:
        data = post_graphql_json(
            graphql_url,
            payload={'query': '{ __schema { types { name kind fields { name } } } }'},
            api_token=api_token,
            timeout=timeout,
        )
    except (requests.RequestException, ValueError) as exc:
        logger.warning('MOLGENIS schema introspection failed: %s', exc)
        return {}

    types = data.get('data', {}).get('__schema', {}).get('types', [])
    skip_suffixes = (
        '_groupBy',
        'GroupBy',
        '_agg',
        'Aggregate',
        '_aggregate',
        'Input',
        'OrderByInput',
        'FilterInput',
        'Connection',
        'Edge',
    )
    skip_prefixes = ('__', '_', 'Molgenis', 'Signin', 'Save')
    skip_names = {
        'Query',
        'Mutation',
        'Subscription',
        'String',
        'Int',
        'Float',
        'Boolean',
        'ID',
        'DateTime',
        'JSON',
    }

    result: dict[str, list[str]] = {}
    for type_info in types:
        name = type_info.get('name', '')
        kind = type_info.get('kind', '')
        if kind != 'OBJECT':
            continue
        if any(name.startswith(prefix) for prefix in skip_prefixes):
            continue
        if name in skip_names:
            continue
        if any(name.endswith(suffix) for suffix in skip_suffixes):
            continue
        if 'Aggregate' in name or 'GroupBy' in name:
            continue

        fields = [
            field['name']
            for field in (type_info.get('fields') or [])
            if not field['name'].startswith('_')
            and not field['name'].endswith('_agg')
            and not field['name'].endswith('_groupBy')
            and not field['name'].endswith('_aggregate')
            and 'mg_' not in field['name']
        ]
        if fields:
            result[name] = sorted(fields)

    return dict(sorted(result.items()))
