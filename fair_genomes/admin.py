"""
Fair Genomes Admin Configuration
"""

from django.contrib import admin

from fair_genomes.models import StatResult


@admin.register(StatResult)
class StatResultAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'column_name', 'last_synced')
    list_filter = ('table_name', 'column_name')
    search_fields = ('table_name', 'column_name')
    readonly_fields = ('distribution', 'last_synced')
    ordering = ('table_name', 'column_name')
