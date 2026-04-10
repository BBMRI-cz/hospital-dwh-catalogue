"""
URL configuration for catalogue project.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views import View


class _GrafanaAuthCheck(View):
    """
    Used exclusively by Nginx auth_request to gate access to /grafana/.
    Returns 200 (staff), 401 (unauthenticated → Nginx redirects to login),
    or 403 (authenticated non-staff → Nginx 403 page).
    The view never renders HTML.
    """

    @staticmethod
    def get(request):
        if not request.user.is_authenticated:
            return HttpResponse(status=401)
        if request.user.is_staff:
            return HttpResponse(status=200)
        return HttpResponse(status=403)


handler404 = 'frontend.views.page_not_found'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/', include('frontend.api_urls')),
    # Internal Nginx auth_request endpoint — must not be publicly reachable
    path('internal/auth/grafana/', _GrafanaAuthCheck.as_view(), name='grafana-auth-check'),
    path('', include('frontend.urls')),
    path('', include('ticketing.urls')),
]
