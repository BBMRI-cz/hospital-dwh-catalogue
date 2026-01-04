"""
Fair Genomes Admin Configuration
"""
from django.contrib import admin
from .models import Personal


@admin.register(Personal)
class PersonalAdmin(admin.ModelAdmin):
    """
    Admin interface for Personal records from Fair Genomes.
    Read-only to prevent accidental modifications to synced data.
    """
    list_display = [
        'personal_identifier',
        'year_of_birth',
        'inserted_by',
        'inserted_on',
        'updated_on'
    ]
    list_filter = ['year_of_birth', 'inserted_on']
    search_fields = ['personal_identifier', 'inserted_by']
    readonly_fields = [
        'personal_identifier',
        'year_of_birth',
        'inserted_by',
        'inserted_on',
        'updated_by',
        'updated_on',
    ]
    ordering = ['-inserted_on']
    
    def has_add_permission(self, request):
        """Disable manual creation - data comes from API sync."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Disable deletion through admin."""
        return False
