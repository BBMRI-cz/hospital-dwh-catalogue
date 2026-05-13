"""Check ALVAO TLS and basic API reachability from the running container."""

from __future__ import annotations

import os
import socket
import ssl
from urllib.parse import urlsplit

import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _configured_cafile() -> str:
    return (
        os.environ.get('REQUESTS_CA_BUNDLE')
        or os.environ.get('SSL_CERT_FILE')
        or ssl.get_default_verify_paths().cafile
        or ''
    )


class Command(BaseCommand):
    help = 'Check ALVAO TLS trust and non-mutating API reachability.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=10)

    def handle(self, *args, **options):
        if getattr(settings, 'MOCK_ALVAO', False):
            self.stdout.write('MOCK_ALVAO=True; skipping ALVAO check.')
            return

        api_url = str(getattr(settings, 'ALVAO_API_URL', '')).rstrip('/')
        if not api_url:
            raise CommandError('ALVAO_API_URL is empty.')

        parsed = urlsplit(api_url)
        if parsed.scheme != 'https' or not parsed.hostname:
            raise CommandError(f'ALVAO_API_URL must be an https URL with a hostname: {api_url}')

        port = parsed.port or 443
        cafile = _configured_cafile()
        if not cafile or not os.path.isfile(cafile):
            raise CommandError(f'Configured CA bundle does not exist: {cafile or "<empty>"}')

        self.stdout.write(f'ALVAO host: {parsed.hostname}:{port}')
        self.stdout.write(f'CA bundle: {cafile}')
        self.stdout.write(f'Service ID: {getattr(settings, "ALVAO_DEFAULT_SERVICE_ID", None)}')
        self.stdout.write(f'SLA ID: {getattr(settings, "ALVAO_DEFAULT_SLA_ID", None)}')

        try:
            context = ssl.create_default_context(cafile=cafile)
            with (
                socket.create_connection(
                    (parsed.hostname, port), timeout=options['timeout']
                ) as sock,
                context.wrap_socket(sock, server_hostname=parsed.hostname) as tls_sock,
            ):
                self.stdout.write(f'TLS protocol: {tls_sock.version()}')
        except Exception as exc:
            raise CommandError(f'ALVAO TLS handshake failed: {exc}') from exc

        ticket_url = f'{api_url}/tickets'
        try:
            response = requests.get(
                ticket_url,
                auth=(
                    getattr(settings, 'ALVAO_SERVICE_ACCOUNT_USERNAME', ''),
                    getattr(settings, 'ALVAO_SERVICE_ACCOUNT_PASSWORD', ''),
                ),
                timeout=options['timeout'],
            )
        except requests.RequestException as exc:
            raise CommandError(f'ALVAO HTTPS request failed: {exc}') from exc

        self.stdout.write(f'ALVAO GET /tickets status: {response.status_code}')
        if response.status_code in {401, 403}:
            raise CommandError(
                'ALVAO is reachable, but the configured service account was rejected.'
            )
        if response.status_code >= 500:
            raise CommandError(f'ALVAO is reachable but returned HTTP {response.status_code}.')

        self.stdout.write(self.style.SUCCESS('ALVAO TLS/reachability check passed.'))
