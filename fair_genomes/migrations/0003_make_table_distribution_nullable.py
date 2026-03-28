import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0002_alter_distribution_dataset_name_table_column'),
    ]

    operations = [
        migrations.AlterField(
            model_name='table',
            name='distribution',
            field=models.ForeignKey(
                blank=True,
                db_column='distribution_name',
                help_text='Distribution this table belongs to (optional — tables synced from GraphQL may have no distribution yet)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tables',
                to='fair_genomes.distribution',
                verbose_name='Distribution',
            ),
        ),
    ]
