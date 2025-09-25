from django.urls import path
from . import views


app_name = 'warehouse'  # Toto definuje namespace

urlpatterns = [
    path('katalog/', views.katalog, name='katalog')
    # Přidejte další URL vzory pro aplikaci warehouse zde
]

