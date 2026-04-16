#!/usr/bin/env python3
"""Health check for the Django login page used by Docker Compose."""

from __future__ import annotations

import http.client
import sys
from urllib.parse import SplitResult, urlsplit

HEALTHCHECK_URL = 'http://localhost:8000/accounts/login/'
TIMEOUT_SECONDS = 5
ALLOWED_SCHEMES = {'http', 'https'}
ALLOWED_HOSTS = {'localhost', '127.0.0.1'}


def get_healthcheck_target() -> tuple[type[http.client.HTTPConnection], str, int, str]:
    parsed: SplitResult = urlsplit(HEALTHCHECK_URL)
    scheme = parsed.scheme.lower()
    host = parsed.hostname

    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f'Unsupported health check scheme: {scheme}')

    if host not in ALLOWED_HOSTS:
        raise ValueError(f'Unsupported health check host: {host}')

    port = parsed.port or (443 if scheme == 'https' else 80)
    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'

    connection_class: type[http.client.HTTPConnection]
    if scheme == 'https':
        connection_class = http.client.HTTPSConnection
    else:
        connection_class = http.client.HTTPConnection

    return connection_class, host, port, path


def main() -> int:
    connection_class, host, port, path = get_healthcheck_target()
    connection = connection_class(host, port, timeout=TIMEOUT_SECONDS)

    try:
        connection.request('GET', path)
        response = connection.getresponse()
        if 200 <= response.status < 400:
            return 0
        print(
            f'Unexpected status code from {HEALTHCHECK_URL}: {response.status}',
            file=sys.stderr,
        )
        return 1
    except (OSError, TimeoutError, ValueError) as exc:
        print(f'Health check failed for {HEALTHCHECK_URL}: {exc}', file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
