from django.urls import path
from . import views

app_name = 'warehouse'  # Application namespace

urlpatterns = [
    path('catalogue/', views.CatalogueView.as_view(), name='catalogue'),
    # Add more URL patterns for the warehouse application here
]
