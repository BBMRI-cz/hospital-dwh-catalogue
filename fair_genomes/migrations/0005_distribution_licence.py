"""
Add the missing licence column to fair_genomes_distribution.

The fair_genomes_distribution table was created before the licence field was
added to DistributionBase (or before 0001_initial was updated to include it).
This migration adds the column so the model and DB schema are back in sync.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0004_alter_catalog_applicable_legislation_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='distribution',
            name='licence',
            field=models.CharField(
                blank=True,
                help_text='dct:license — licence under which this distribution is made available',
                max_length=500,
                null=True,
                verbose_name='Licence',
            ),
        ),
    ]
