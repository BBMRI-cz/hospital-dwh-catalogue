import logging
import time

from django.conf import settings

logger = logging.getLogger('catalogue.request')


class RequestLoggingMiddleware:
    """
    Logs every HTTP request: method, path, status code, duration and authenticated user.
    Issues WARNING instead of INFO for slow requests exceeding LOG_SLOW_REQUEST_THRESHOLD_S.
    Extra fields are passed as structured `extra=` so JSON handlers emit them as top-level keys.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_threshold_ms = getattr(settings, 'LOG_SLOW_REQUEST_THRESHOLD_S', 1.0) * 1000

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        user = getattr(request, 'user', None)
        username = user.get_username() if user and user.is_authenticated else 'anonymous'

        msg = f'{request.method} {request.path} {response.status_code} {duration_ms}ms user={username}'
        extra = {
            'http_method': request.method,
            'http_path': request.path,
            'http_status': response.status_code,
            'duration_ms': duration_ms,
            'username': username,
        }

        if duration_ms >= self.slow_threshold_ms:
            logger.warning('Slow request: %s', msg, extra=extra)
        else:
            logger.info(msg, extra=extra)

        return response
