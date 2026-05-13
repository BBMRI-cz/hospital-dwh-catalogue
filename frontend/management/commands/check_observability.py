"""Check that Django file logs are reaching Loki."""

from __future__ import annotations

import json
import logging
import time
import uuid
from urllib.parse import urlencode
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Emit a Django log line and verify that Loki receives it.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loki-url',
            default='http://loki:3100',
            help='Base URL for Loki from inside the Docker network.',
        )
        parser.add_argument('--timeout', type=int, default=30)

    def handle(self, *args, **options):
        marker = f'deploy-observability-check-{uuid.uuid4().hex}'
        timeout = options['timeout']
        loki_url = str(options['loki_url']).rstrip('/')
        logger = logging.getLogger('catalogue.deploy')

        logger.info('Post-deploy observability check marker=%s', marker)
        for logger_name in ('', 'catalogue', 'catalogue.deploy'):
            for handler in logging.getLogger(logger_name).handlers:
                handler.flush()

        query = urlencode({'query': f'{{app="hospital-dwh-catalogue"}} |= "{marker}"'})
        url = f'{loki_url}/loki/api/v1/query?{query}'
        deadline = time.monotonic() + timeout
        last_error = ''

        while time.monotonic() < deadline:
            try:
                with urlopen(url, timeout=5) as response:
                    payload = json.loads(response.read().decode('utf-8'))
            except Exception as exc:  # pragma: no cover - depends on Docker network
                last_error = str(exc)
            else:
                if payload.get('data', {}).get('result'):
                    self.stdout.write(self.style.SUCCESS('Observability check passed.'))
                    return
                last_error = 'marker not found in Loki yet'

            time.sleep(2)

        raise CommandError(f'Observability check failed: {last_error}')
