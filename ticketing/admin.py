"""
Admin configuration for the ticketing application.
"""
from django.contrib import admin

from .models import TicketRequest, TicketRequestItem


class TicketRequestItemInline(admin.TabularInline):
    """Inline admin for ticket request items."""
    
    model = TicketRequestItem
    extra = 0
    readonly_fields = ['item_type', 'item_id', 'item_name', 'item_description']


@admin.register(TicketRequest)
class TicketRequestAdmin(admin.ModelAdmin):
    """Admin configuration for TicketRequest model."""
    
    list_display = [
        'id', 'requester_email', 'status', 'alvao_ticket_id',
        'created_at', 'submitted_at'
    ]
    list_filter = ['status', 'created_at', 'submitted_at']
    search_fields = ['requester_email', 'requester_name', 'alvao_ticket_id', 'subject']
    readonly_fields = [
        'id', 'alvao_ticket_id', 'alvao_response', 'created_at',
        'updated_at', 'submitted_at'
    ]
    ordering = ['-created_at']
    inlines = [TicketRequestItemInline]
    
    fieldsets = (
        (None, {
            'fields': ('requester_email', 'requester_name', 'subject', 'description')
        }),
        ('Status', {
            'fields': ('status', 'alvao_ticket_id', 'alvao_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'submitted_at'),
            'classes': ('collapse',)
        }),
    )
