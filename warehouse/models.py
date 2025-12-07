from django.db import models


class DatasourceList(models.Model):
    """Data sources for the warehouse catalog"""
    data_source = models.CharField(max_length=50, primary_key=True)
    data_source_name = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        managed = False  # Don't let Django manage this table
        db_table = 'datasource_list'

    def __str__(self):
        return self.data_source_name or self.data_source


class DatasetList(models.Model):
    """Datasets within data sources"""
    data_source = models.ForeignKey(
        DatasourceList,
        on_delete=models.RESTRICT,
        db_column='data_source',
        null=True,
        blank=True,
        related_name='datasets'
    )
    data_set = models.CharField(max_length=100, primary_key=True)
    data_set_name = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    author = models.CharField(max_length=100, null=True, blank=True)
    contributor = models.CharField(max_length=100, null=True, blank=True)
    publisher = models.CharField(max_length=100, null=True, blank=True)
    rights_holder = models.CharField(max_length=100, null=True, blank=True)
    provenance = models.TextField(null=True, blank=True)
    complete = models.CharField(max_length=3, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'dataset_list'

    def __str__(self):
        return self.data_set_name or self.data_set


class DataclassList(models.Model):
    """Data classes within datasets"""
    data_set = models.ForeignKey(
        DatasetList,
        on_delete=models.RESTRICT,
        db_column='data_set',
        null=True,
        blank=True,
        related_name='dataclasses'
    )
    data_class = models.CharField(max_length=100, primary_key=True)
    data_class_name = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    file_extension = models.CharField(max_length=50, null=True, blank=True)
    resource_type = models.CharField(max_length=50, null=True, blank=True)
    resource_content = models.CharField(max_length=50, null=True, blank=True)
    data_confidentality = models.CharField(max_length=100, null=True, blank=True)
    language_code = models.CharField(max_length=50, null=True, blank=True)
    provenance = models.TextField(null=True, blank=True)
    data_quality = models.CharField(max_length=100, null=True, blank=True)
    repository = models.CharField(max_length=5, null=True, blank=True)
    complete = models.CharField(max_length=5, null=True, blank=True)
    etl = models.CharField(max_length=5, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'dataclass_list'

    def __str__(self):
        return self.data_class_name or self.data_class


class DataclassTableSchemes(models.Model):
    """Column definitions for data class tables"""
    data_class = models.ForeignKey(
        DataclassList,
        on_delete=models.RESTRICT,
        db_column='data_class',
        related_name='table_schemes'
    )
    col_order = models.SmallIntegerField()
    col_var = models.CharField(max_length=100, null=True, blank=True)
    col_name = models.CharField(max_length=255, null=True, blank=True)
    col_description = models.TextField(null=True, blank=True)
    col_var_r = models.CharField(max_length=100, null=True, blank=True)
    col_transf_r = models.SmallIntegerField(null=True, blank=True)
    datatype_r = models.CharField(max_length=20, null=True, blank=True)
    possible_key = models.CharField(max_length=100, null=True, blank=True)
    tag = models.CharField(max_length=100, null=True, blank=True)
    confidentality = models.SmallIntegerField(null=True, blank=True)
    vocabulary = models.TextField(null=True, blank=True)
    calculated = models.SmallIntegerField(null=True, blank=True)
    madatory = models.SmallIntegerField(null=True, blank=True)
    unit = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'dataclass_table_schemes'
        unique_together = [['data_class', 'col_order']]
        ordering = ['col_order']

    def __str__(self):
        return f"{self.data_class_id} - {self.col_name}"


class DbTableList(models.Model):
    """Database tables in the warehouse"""
    data_class = models.ForeignKey(
        DataclassList,
        on_delete=models.RESTRICT,
        db_column='data_class',
        null=True,
        blank=True,
        related_name='db_tables'
    )
    db_layer = models.CharField(max_length=50, null=True, blank=True)
    db_table = models.CharField(max_length=100, primary_key=True)
    db_table_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    datetime_created = models.DateField(null=True, blank=True)
    datetime_last_modified = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'db_table_list'

    def __str__(self):
        return self.db_table_name or self.db_table


class DbTableSchemes(models.Model):
    """Column definitions for database tables"""
    db_table = models.ForeignKey(
        DbTableList,
        on_delete=models.RESTRICT,
        db_column='db_table',
        related_name='schemes'
    )
    var_order = models.SmallIntegerField(null=True, blank=True)
    var = models.CharField(max_length=100)
    key_db = models.CharField(max_length=100, null=True, blank=True)
    type_db = models.CharField(max_length=20, null=True, blank=True)
    type_r = models.CharField(max_length=20, null=True, blank=True)
    var_name = models.CharField(max_length=255, null=True, blank=True)
    var_description = models.TextField(null=True, blank=True)
    vocabulary = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'db_table_schemes'
        unique_together = [['db_table', 'var']]
        ordering = ['var_order']

    def __str__(self):
        return f"{self.db_table_id} - {self.var_name}"
