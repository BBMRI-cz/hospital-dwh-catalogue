"""
URL configuration for the ticketing application.
"""

from django.urls import path

from . import views

app_name = 'ticketing'

urlpatterns = [
    # Cart management
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/add/', views.AddToCartView.as_view(), name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('cart/clear/', views.ClearCartView.as_view(), name='clear_cart'),
    path('cart/submit/', views.SubmitCartView.as_view(), name='submit_cart'),
    path('cart/count/', views.CartCountView.as_view(), name='cart_count'),
    path('cart/items/', views.CartItemsView.as_view(), name='cart_items'),
    # Ticket views
    path('submitted/', views.TicketSubmittedView.as_view(), name='ticket_submitted'),
    path('my-tickets/', views.MyTicketsView.as_view(), name='my_tickets'),
    path('tickets/<int:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
]
