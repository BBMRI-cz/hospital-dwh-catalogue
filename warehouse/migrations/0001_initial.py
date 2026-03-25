import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ContactPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(blank=True, help_text='Contact e-mail address (vcard:hasEmail). Store as plain email (e.g. user@example.org); exported as mailto: URI on RDF output. At least one of email or contact_page is required.', max_length=255, null=True, verbose_name='Email')),
                ('contact_page', models.CharField(blank=True, help_text='URL of a web page that can be used to reach the contact (vcard:hasURL). Must be a URI/IRI. At least one of email or contact_page is required.', max_length=500, null=True, verbose_name='Contact Page')),
            ],
            options={
                'verbose_name': 'Contact Point',
                'verbose_name_plural': 'Contact Points',
                'db_table': 'metadata"."lm_contact_point',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('name', models.CharField(help_text='Unique identifier / name for this agent', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('description', models.TextField(blank=True, help_text="dct:description — description of the agent's activities (0..*)", null=True, verbose_name='Description')),
                ('contact_point', models.ForeignKey(blank=True, help_text='Contact information for this agent', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agents', to='warehouse.contactpoint', verbose_name='Contact Point')),
            ],
            options={
                'verbose_name': 'Agent',
                'verbose_name_plural': 'Agents',
                'db_table': 'metadata"."lm_agent',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Catalog',
            fields=[
                ('name', models.CharField(help_text='Unique identifier for this catalog', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('title', models.CharField(help_text='dct:title — mandatory per HealthDCAT-AP v6 (1..*)', max_length=500, null=True, verbose_name='Title')),
                ('description', models.TextField(help_text='dct:description — mandatory per HealthDCAT-AP v6 (1..*)', null=True, verbose_name='Description')),
                ('applicable_legislation', models.CharField(help_text='Legal basis under which this catalog is published — must be a URI/IRI (mandatory per HealthDCAT-AP v6, e.g. http://data.europa.eu/eli/reg/2022/868/oj)', max_length=500, verbose_name='Applicable Legislation')),
                ('publisher', models.ForeignKey(blank=True, help_text='Agent responsible for making this catalog available', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='catalogs', to='warehouse.agent', verbose_name='Publisher')),
            ],
            options={
                'verbose_name': 'Catalog',
                'verbose_name_plural': 'Catalogs',
                'db_table': 'metadata"."lm_catalog',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Dataset',
            fields=[
                ('name', models.CharField(help_text='Unique identifier for this dataset', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('title', models.CharField(help_text='dct:title — mandatory per HealthDCAT-AP v6 (1..*)', max_length=500, null=True, verbose_name='Title')),
                ('version', models.CharField(blank=True, max_length=100, null=True, verbose_name='Version')),
                ('description', models.TextField(help_text='dct:description — mandatory per HealthDCAT-AP v6 (1..*)', null=True, verbose_name='Description')),
                ('identifier', models.CharField(help_text='dct:identifier — canonical URI of this dataset from the origin system (mandatory per HealthDCAT-AP v6, 1..*)', max_length=500, verbose_name='Identifier')),
                ('type', models.CharField(help_text='dct:type — dataset type URI from EU Dataset-type vocabulary; comma-separated when multiple, e.g. http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL (mandatory per HealthDCAT-AP v6, 1..*)', max_length=500, verbose_name='Type')),
                ('theme', models.CharField(help_text='dcat:theme — must be a URI/IRI from the EU data-theme vocabulary; mandatory per HealthDCAT-AP v6 (1..*), e.g. http://publications.europa.eu/resource/authority/data-theme/HEAL', max_length=500, null=True, verbose_name='Theme')),
                ('conforms_to', models.CharField(blank=True, help_text='dct:conformsTo — standard / specification URI', max_length=500, null=True, verbose_name='Conforms To')),
                ('issued', models.DateTimeField(blank=True, help_text='dct:issued — date of first publication', null=True, verbose_name='Issued')),
                ('modified', models.DateTimeField(blank=True, help_text='dct:modified — date of last modification', null=True, verbose_name='Modified')),
                ('keyword', models.TextField(help_text='dcat:keyword — comma-separated keywords (mandatory per HealthDCAT-AP v6, 1..*)', null=True, verbose_name='Keywords')),
                ('source', models.TextField(blank=True, help_text='dct:source — URI of the source dataset', null=True, verbose_name='Source')),
                ('creator', models.TextField(blank=True, help_text='dct:creator — name(s) of the dataset creator(s)', null=True, verbose_name='Creator')),
                ('provenance', models.TextField(help_text='dct:provenance — mandatory per HealthDCAT-AP v6 (1..*)', null=True, verbose_name='Provenance')),
                ('access_rights', models.CharField(help_text='dct:accessRights — controlled vocabulary URI (mandatory per HealthDCAT-AP v6)', max_length=500, verbose_name='Access Rights')),
                ('applicable_legislation', models.CharField(help_text='dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, e.g. http://data.europa.eu/eli/reg/2022/868/oj)', max_length=500, verbose_name='Applicable Legislation')),
                ('health_category', models.CharField(help_text='healthdcat:healthCategory — must be a URI/IRI (mandatory per HealthDCAT-AP v6, e.g. https://healthdataportal.eu/categorisation/Health-care-delivery)', max_length=500, verbose_name='Health Category')),
                ('catalog', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='datasets', to='warehouse.catalog', verbose_name='Catalog')),
                ('contact_point', models.ForeignKey(help_text='dcat:contactPoint — mandatory per HealthDCAT-AP v6 (1..*)', on_delete=django.db.models.deletion.PROTECT, related_name='datasets', to='warehouse.contactpoint', verbose_name='Contact Point')),
                ('custodian', models.ForeignKey(blank=True, help_text='geodcatap:custodian — agent responsible for maintaining this dataset (HealthDCAT-AP Release 6, optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='custodian_datasets', to='warehouse.agent', verbose_name='Custodian')),
                ('hdab', models.ForeignKey(help_text='healthdcat:hdab — Health Data Access Body responsible for this dataset (mandatory per HealthDCAT-AP v6)', on_delete=django.db.models.deletion.PROTECT, related_name='hdab_datasets', to='warehouse.agent', verbose_name='HDAB')),
                ('publisher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='published_datasets', to='warehouse.agent', verbose_name='Publisher')),
            ],
            options={
                'verbose_name': 'Dataset',
                'verbose_name_plural': 'Datasets',
                'db_table': 'metadata"."lm_dataset',
                'ordering': ['name'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Distribution',
            fields=[
                ('name', models.CharField(help_text='Unique identifier for this distribution', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('title', models.CharField(blank=True, max_length=500, null=True, verbose_name='Title')),
                ('description', models.TextField(blank=True, null=True, verbose_name='Description')),
                ('format', models.CharField(blank=True, help_text='dct:format — media type or format URI', max_length=100, null=True, verbose_name='Format')),
                ('conforms_to', models.CharField(blank=True, max_length=500, null=True, verbose_name='Conforms To')),
                ('byte_size', models.BigIntegerField(blank=True, help_text='dcat:byteSize', null=True, verbose_name='Byte Size')),
                ('rights', models.CharField(blank=True, help_text='dct:rights', max_length=500, null=True, verbose_name='Rights')),
                ('issued', models.DateTimeField(blank=True, null=True, verbose_name='Issued')),
                ('modified', models.DateTimeField(blank=True, null=True, verbose_name='Modified')),
                ('access_url', models.CharField(help_text='dcat:accessURL (mandatory per HealthDCAT-AP v6)', max_length=500, verbose_name='Access URL')),
                ('applicable_legislation', models.CharField(help_text='dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, e.g. http://data.europa.eu/eli/reg/2022/868/oj)', max_length=500, verbose_name='Applicable Legislation')),
                ('licence', models.CharField(blank=True, help_text='dct:license — licence under which this distribution is made available', max_length=500, null=True, verbose_name='Licence')),
                ('db_layer', models.CharField(blank=True, help_text='Physical DWH layer this distribution resides in (e.g. raw, clean, analytical). Local Metadata-specific field.', max_length=100, null=True, verbose_name='DB Layer')),
                ('dataset_name', models.ForeignKey(db_column='dataset_name', help_text='Dataset this distribution belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='distributions', to='warehouse.dataset', to_field='name', verbose_name='Dataset')),
            ],
            options={
                'verbose_name': 'Distribution',
                'verbose_name_plural': 'Distributions',
                'db_table': 'metadata"."lm_distribution',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Table',
            fields=[
                ('name', models.CharField(help_text='csvw:name — unique identifier for this table', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('url', models.CharField(help_text='csvw:url — physical location / connection string for this table', max_length=500, verbose_name='URL')),
                ('title', models.CharField(blank=True, help_text='csvw:title — human-readable table name', max_length=500, null=True, verbose_name='Title')),
                ('description', models.TextField(blank=True, help_text='dct:description', null=True, verbose_name='Description')),
                ('distribution', models.ForeignKey(db_column='distribution_name', help_text='Distribution this table belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='tables', to='warehouse.distribution', to_field='name', verbose_name='Distribution')),
            ],
            options={
                'verbose_name': 'Table',
                'verbose_name_plural': 'Tables',
                'db_table': 'metadata"."lm_table',
                'ordering': ['name'],
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Column',
            fields=[
                ('name', models.CharField(help_text='csvw:name — unique column identifier', max_length=255, primary_key=True, serialize=False, verbose_name='Name')),
                ('title', models.CharField(help_text='csvw:title — human-readable column name', max_length=500, verbose_name='Title')),
                ('description', models.TextField(help_text='dct:description', verbose_name='Description')),
                ('datatype', models.CharField(help_text='csvw:datatype — column datatype (e.g. VARCHAR, INTEGER, DATE)', max_length=100, verbose_name='Datatype')),
                ('property_url', models.CharField(blank=True, help_text='csvw:propertyUrl — semantic property URI', max_length=500, null=True, verbose_name='Property URL')),
                ('var_order', models.SmallIntegerField(blank=True, help_text='Position of this column in the source table', null=True, verbose_name='Variable Order')),
                ('key_db', models.CharField(blank=True, help_text='Primary / foreign key indicator from the DB schema', max_length=100, null=True, verbose_name='DB Key')),
                ('type_r', models.CharField(blank=True, help_text='Corresponding R datatype for analytical use', max_length=50, null=True, verbose_name='R Type')),
                ('definition_ddl', models.TextField(blank=True, help_text='Full DDL column definition', null=True, verbose_name='DDL Definition')),
                ('definition_pk_pom1', models.TextField(blank=True, null=True, verbose_name='PK Definition (helper 1)')),
                ('definition_pk_pom2', models.TextField(blank=True, null=True, verbose_name='PK Definition (helper 2)')),
                ('definition_pk', models.TextField(blank=True, help_text='Primary key definition expression', null=True, verbose_name='PK Definition')),
                ('table', models.ForeignKey(db_column='table_name', help_text='Table this column belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='columns', to='warehouse.table', to_field='name', verbose_name='Table')),
            ],
            options={
                'verbose_name': 'Column',
                'verbose_name_plural': 'Columns',
                'db_table': 'metadata"."lm_column',
                'ordering': ['var_order', 'name'],
                'managed': False,
            },
        ),
    ]
