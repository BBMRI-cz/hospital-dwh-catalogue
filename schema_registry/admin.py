"""
Schema Registry Admin — registers all four models with basic list_display.
"""

from django.contrib import admin

from schema_registry.models import SchemaFieldBinding, SchemaPrefix, SchemaTerm, SchemaVersion


@admin.register(SchemaVersion)
class SchemaVersionAdmin(admin.ModelAdmin):
    list_display = ('slug', 'label', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('slug', 'label')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SchemaPrefix)
class SchemaPrefixAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'base_uri', 'schema_version')
    list_filter = ('schema_version',)
    search_fields = ('prefix', 'base_uri')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SchemaTerm)
class SchemaTermAdmin(admin.ModelAdmin):
    list_display = ('term_key', 'semantics', 'uri', 'requirement', 'display_order', 'schema_version')
    list_filter = ('schema_version', 'requirement')
    search_fields = ('term_key', 'semantics', 'base_label_en')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SchemaFieldBinding)
class SchemaFieldBindingAdmin(admin.ModelAdmin):
    list_display = ('table_name', 'column_name', 'column_type', 'label_en', 'is_entity', 'display_order', 'schema_version')
    list_filter = ('schema_version', 'table_name', 'is_entity')
    search_fields = ('table_name', 'column_name', 'label_en')
    readonly_fields = ('created_at', 'updated_at')
