"""
Admin configuration for the ticketing application.
"""

from django.contrib import admin

from ticketing.models import TicketRequest, TicketRequestItem


class TicketRequestItemInline(admin.TabularInline):
    model = TicketRequestItem
    extra = 0
    readonly_fields = ('item_type', 'item_id', 'item_name', 'parent_dataset', 'added_at')


@admin.register(TicketRequest)
class TicketRequestAdmin(admin.ModelAdmin):
    list_display = (
        'subject',
        'requester',
        'requester_email',
        'status',
        'alvao_ticket_id',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'requester_email', 'requester_name', 'alvao_ticket_id')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at')
    inlines = [TicketRequestItemInline]


@admin.register(TicketRequestItem)
class TicketRequestItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'item_type', 'ticket_request', 'parent_dataset', 'added_at')
    list_filter = ('item_type',)
    search_fields = ('item_name', 'item_id', 'parent_dataset')
