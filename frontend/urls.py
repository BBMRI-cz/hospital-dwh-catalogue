"""URL patterns for the frontend app."""

from django.urls import path

from frontend import views

app_name = 'frontend'

urlpatterns = [
    path('', views.CatalogueIndexView.as_view(), name='catalogue'),
    path('dataset/<str:app>/<str:name>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path(
        'dataset/<str:app>/<str:name>/rdf/',
        views.DatasetRdfExportView.as_view(),
        name='dataset_rdf_export',
    ),
    path(
        'distribution/<str:app>/<str:name>/',
        views.DistributionDetailView.as_view(),
        name='distribution_detail',
    ),
]
