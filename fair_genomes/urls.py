"""
Fair Genomes URL Configuration
"""
from django.urls import path
from .views import PersonalListView, PersonalDetailView

app_name = 'fair_genomes'

urlpatterns = [
    path('', PersonalListView.as_view(), name='personal_list'),
    path('<str:pk>/', PersonalDetailView.as_view(), name='personal_detail'),
]
