import logging
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import resolve_url

logger = logging.getLogger('catalogue.request')


class HtmxLoginRedirectMiddleware:
    """
    Convert HTMX login redirects into full-page browser redirects.

    Without this, an expired session makes HTMX follow Django's 302 to the
    login page and swap the login HTML into the small target element.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.headers.get('HX-Request') != 'true':
            return response

        if response.status_code not in {301, 302, 303, 307, 308}:
            return response

        redirect_url = response.headers.get('Location')
        if not redirect_url or not _is_login_redirect(redirect_url):
            return response

        htmx_response = HttpResponse(status=204)
        htmx_response['HX-Redirect'] = redirect_url
        return htmx_response


def _is_login_redirect(redirect_url: str) -> bool:
    login_path = urlsplit(resolve_url(settings.LOGIN_URL)).path
    redirect_path = urlsplit(redirect_url).path
    return redirect_path == login_path


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
