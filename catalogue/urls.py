"""
URL configuration for catalogue project.
"""

from django.contrib import admin
from django.urls import include, path

handler404 = 'warehouse.views.page_not_found'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('warehouse.urls')),
    path('', include('ticketing.urls')),
]
