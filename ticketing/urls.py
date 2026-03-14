"""URL patterns for the ticketing app."""

from django.urls import path

from ticketing import views

app_name = 'ticketing'

urlpatterns = [
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.CartAddView.as_view(), name='cart_add'),
    path('cart/remove/', views.CartRemoveView.as_view(), name='cart_remove'),
    path('tickets/', views.TicketHistoryView.as_view(), name='ticket_history'),
]
