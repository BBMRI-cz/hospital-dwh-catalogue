from django.urls import path
from . import views

app_name = 'warehouse'  # Application namespace

urlpatterns = [
    path('', views.CatalogueView.as_view(), name='catalogue'),
]
