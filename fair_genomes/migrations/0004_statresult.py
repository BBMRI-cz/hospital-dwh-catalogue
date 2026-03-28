from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0003_make_table_distribution_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='StatResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('table_name', models.CharField(
                    help_text='MOLGENIS table name, e.g. "sequencing"',
                    max_length=100,
                    verbose_name='Table name',
                )),
                ('column_name', models.CharField(
                    help_text='Unqualified column name, e.g. "sequencinginstrumentmodel"',
                    max_length=200,
                    verbose_name='Column name',
                )),
                ('filter_value', models.CharField(
                    help_text='The value that was counted, e.g. "MiSeq"',
                    max_length=500,
                    verbose_name='Filter value',
                )),
                ('count', models.IntegerField(
                    blank=True,
                    null=True,
                    help_text='Number of records matching the filter; null means not yet synced',
                    verbose_name='Count',
                )),
                ('last_synced', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Last synced',
                )),
            ],
            options={
                'verbose_name': 'Stat Result',
                'verbose_name_plural': 'Stat Results',
                'db_table': 'fair_genomes_stat_result',
                'ordering': ['table_name', 'column_name', 'filter_value'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='statresult',
            unique_together={('table_name', 'column_name', 'filter_value')},
        ),
    ]
