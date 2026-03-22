"""
HealthDCAT-AP Release 6: add geodcatap:custodian to Dataset.

custodian is an optional FK to Agent representing the agent responsible
for maintaining this dataset (geodcatap:custodian).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0002_healthdcat_ap_v6'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='custodian',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'geodcatap:custodian \u2014 agent responsible for maintaining this dataset '
                    '(HealthDCAT-AP Release 6, optional)'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='custodian_datasets',
                to='fair_genomes.agent',
                verbose_name='Custodian',
            ),
        ),
    ]
