from django.db import models
from django.utils.translation import gettext_lazy as _

class DatasourceList(models.Model):
    """Data sources for the warehouse catalogue"""
    data_source = models.CharField(max_length=50, primary_key=True)
    data_source_name = models.CharField(max_length=255, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'metadata"."datasource_list'
        verbose_name = _('Data Source')
        verbose_name_plural = _('Data Sources')

    def __str__(self):
        return self.data_source_name or self.data_source
    
    @property
    def display_name(self):
        """Returns the display name for the data source"""
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
        db_table = 'metadata"."dataset_list'
        verbose_name = _('Dataset')
        verbose_name_plural = _('Datasets')
        ordering = ['data_set_name']

    def __str__(self):
        return self.data_set_name or self.data_set
    
    @property
    def display_name(self):
        """Returns the display name for the dataset"""
        return self.data_set_name or self.data_set
    
    @property
    def is_complete(self):
        """Check if dataset is complete"""
        return self.complete and self.complete.lower() == 'ano'
    
    @property
    def subject_tags_list(self):
        """Returns list of subject tags"""
        if not self.subject:
            return []
        return [tag.strip() for tag in self.subject.split(',') if tag.strip()]
    
    @property
    def has_tables(self):
        """Check if dataset has database tables"""
        return any(dc.has_tables for dc in self.dataclasses.all())
    
    @property
    def has_classes(self):
        """Check if dataset has data classes with repositories"""
        return any(dc.has_repository for dc in self.dataclasses.all())
    
    @property
    def availability_status(self):
        """Returns the availability status of the dataset"""
        if self.has_tables:
            return 'tables'
        elif self.has_classes:
            return 'classes'
        return 'none'


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
        db_table = 'metadata"."dataclass_list'
        verbose_name = _('Data Class')
        verbose_name_plural = _('Data Classes')
        ordering = ['data_class_name']

    def __str__(self):
        return self.data_class_name or self.data_class
    
    @property
    def display_name(self):
        """Returns the display name for the data class"""
        return self.data_class_name or self.data_class
    
    @property
    def is_complete(self):
        """Check if data class is complete"""
        return self.complete and self.complete.lower() == 'ano'
    
    @property
    def has_repository(self):
        """Check if data class has a repository"""
        return bool(self.repository and self.repository.strip())
    
    @property
    def has_tables(self):
        """Check if data class has database tables"""
        return self.db_tables.exists()
    
    @property
    def table_schemes_cache(self):
        """Lazy load table schemes for this data class"""
        if not hasattr(self, '_table_schemes_cache'):
            self._table_schemes_cache = list(
                DataclassTableSchemes.objects
                .filter(data_class=self.data_class)
                .order_by('col_order')
            )
        return self._table_schemes_cache


class DataclassTableSchemes(models.Model):
    """Column definitions for data class tables."""
    pk = models.CompositePrimaryKey('data_class', 'col_order')
    data_class = models.CharField(
        max_length=100,
        db_column='data_class',
        verbose_name=_('Data Class')
    )
    col_order = models.SmallIntegerField(verbose_name=_('Column Order'))
    col_var = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Column Variable')
    )
    col_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Column Name')
    )
    col_description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Column Description')
    )
    col_var_r = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('R Variable')
    )
    col_transf_r = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('R Transformation')
    )
    datatype_r = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_('R Datatype')
    )
    possible_key = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Possible Key')
    )
    tag = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Tag')
    )
    confidentality = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Confidentiality Level')
    )
    vocabulary = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Vocabulary')
    )
    calculated = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Calculated')
    )
    mandatory = models.SmallIntegerField(
        null=True,
        blank=True,
        db_column='madatory',  # Note: preserves original DB column spelling
        verbose_name=_('Mandatory')
    )
    unit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_('Unit')
    )

    class Meta:
        managed = False
        db_table = 'metadata"."dataclass_table_schemes'
        verbose_name = _('Data Class Table Schema')
        verbose_name_plural = _('Data Class Table Schemas')
        ordering = ['col_order']

    def __str__(self):
        return f"{self.data_class} - {self.col_name}"


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
        db_table = 'metadata"."db_table_list'
        verbose_name = _('Database Table')
        verbose_name_plural = _('Database Tables')
        ordering = ['db_table_name']

    def __str__(self):
        return self.db_table_name or self.db_table
    
    @property
    def display_name(self):
        """Returns the display name for the table"""
        return self.db_table_name or self.db_table
    
    @property
    def schemes_cache(self):
        """Lazy load table schemes for this database table"""
        if not hasattr(self, '_schemes_cache'):
            self._schemes_cache = list(
                DbTableSchemes.objects
                .filter(db_table=self.db_table)
                .order_by('var_order')
            )
        return self._schemes_cache


class DbTableSchemes(models.Model):
    """Column definitions for database tables."""
    pk = models.CompositePrimaryKey('db_table', 'var')
    db_table = models.CharField(
        max_length=100,
        db_column='db_table',
        verbose_name=_('Database Table')
    )
    var_order = models.SmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Variable Order')
    )
    var = models.CharField(
        max_length=100,
        verbose_name=_('Variable')
    )
    key_db = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Database Key')
    )
    type_db = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_('Database Type')
    )
    type_r = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_('R Type')
    )
    var_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Variable Name')
    )
    var_description = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Variable Description')
    )
    vocabulary = models.TextField(
        null=True,
        blank=True,
        verbose_name=_('Vocabulary')
    )

    class Meta:
        managed = False
        db_table = 'metadata"."db_table_schemes'
        verbose_name = _('Database Table Schema')
        verbose_name_plural = _('Database Table Schemas')
        ordering = ['var_order']

    def __str__(self):
        return f"{self.db_table} - {self.var_name}"
