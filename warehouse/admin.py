from django.contrib import admin
from .models import (
    DatasourceList, DatasetList, DataclassList,
    DbTableList, DataclassTableSchemes, DbTableSchemes
)


@admin.register(DatasourceList)
class DatasourceListAdmin(admin.ModelAdmin):
    """Admin configuration for DatasourceList"""
    list_display = ['data_source', 'data_source_name', 'subject']
    search_fields = ['data_source', 'data_source_name', 'subject', 'description']
    list_filter = ['subject']
    readonly_fields = ['data_source']  # Primary key should be readonly


@admin.register(DatasetList)
class DatasetListAdmin(admin.ModelAdmin):
    """Admin configuration for DatasetList"""
    list_display = ['data_set', 'data_set_name', 'data_source', 'rights_holder', 'is_complete']
    search_fields = ['data_set', 'data_set_name', 'description', 'subject']
    list_filter = ['data_source', 'rights_holder', 'complete']
    readonly_fields = ['data_set']
    
    def is_complete(self, obj):
        return obj.is_complete
    is_complete.boolean = True
    is_complete.short_description = 'Complete'


@admin.register(DataclassList)
class DataclassListAdmin(admin.ModelAdmin):
    """Admin configuration for DataclassList"""
    list_display = ['data_class', 'data_class_name', 'data_set', 'file_extension', 'is_complete']
    search_fields = ['data_class', 'data_class_name', 'description']
    list_filter = ['data_set', 'file_extension', 'complete', 'repository']
    readonly_fields = ['data_class']
    
    def is_complete(self, obj):
        return obj.is_complete
    is_complete.boolean = True
    is_complete.short_description = 'Complete'


class DataclassTableSchemesInline(admin.TabularInline):
    """Inline admin for table schemes"""
    model = DataclassTableSchemes
    extra = 0
    fields = ['col_order', 'col_var', 'col_name', 'col_description', 'datatype_r']
    ordering = ['col_order']


@admin.register(DbTableList)
class DbTableListAdmin(admin.ModelAdmin):
    """Admin configuration for DbTableList"""
    list_display = ['db_table', 'db_table_name', 'data_class', 'db_layer', 'datetime_last_modified']
    search_fields = ['db_table', 'db_table_name', 'description']
    list_filter = ['db_layer', 'data_class']
    readonly_fields = ['db_table', 'datetime_created', 'datetime_last_modified']
    date_hierarchy = 'datetime_last_modified'


class DbTableSchemesInline(admin.TabularInline):
    """Inline admin for database table schemes"""
    model = DbTableSchemes
    extra = 0
    fields = ['var_order', 'var', 'var_name', 'type_db', 'key_db']
    ordering = ['var_order']
