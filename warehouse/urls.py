"""URL patterns for the warehouse (catalogue) app."""

from django.urls import path

from warehouse import views

app_name = 'warehouse'

urlpatterns = [
    path('', views.CatalogueIndexView.as_view(), name='catalogue'),
    path('dataset/<str:app>/<str:name>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path(
        'distribution/<str:app>/<str:name>/',
        views.DistributionDetailView.as_view(),
        name='distribution_detail',
    ),
]
