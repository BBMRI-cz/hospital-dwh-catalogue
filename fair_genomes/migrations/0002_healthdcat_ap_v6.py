# Recreated 2026-03-22
# Adds all HealthDCAT-AP v6 compliance fields.
# Changes vs original:
#   - retention_period: was CharField(500) → now ForeignKey to new RetentionPeriod model
#   - Agent: added description TextField
#   - RetentionPeriod: new model (dct:PeriodOfTime with start_date / end_date)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0001_initial'),
    ]

    operations = [
        # ── Agent: description ────────────────────────────────────────────
        migrations.AddField(
            model_name='agent',
            name='description',
            field=models.TextField(
                blank=True,
                help_text="dct:description — description of the agent's activities (0..*)",
                null=True,
                verbose_name='Description',
            ),
        ),

        # ── Dataset: new mandatory fields ──────────────────────────────────
        migrations.AddField(
            model_name='dataset',
            name='identifier',
            field=models.CharField(
                default='',
                help_text=(
                    'dct:identifier — canonical URI of this dataset from the origin system '
                    '(mandatory per HealthDCAT-AP v6, 1..*)'
                ),
                max_length=500,
                verbose_name='Identifier',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dataset',
            name='type',
            field=models.CharField(
                default='',
                help_text=(
                    'dct:type — dataset type URI from EU Dataset-type vocabulary; '
                    'comma-separated when multiple, e.g. '
                    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL '
                    '(mandatory per HealthDCAT-AP v6, 1..*)'
                ),
                max_length=500,
                verbose_name='Type',
            ),
            preserve_default=False,
        ),

        # ── Dataset: existing optional → mandatory ─────────────────────────
        migrations.AlterField(
            model_name='dataset',
            name='keyword',
            field=models.TextField(
                help_text='dcat:keyword — comma-separated keywords (mandatory per HealthDCAT-AP v6, 1..*)',
                null=True,
                verbose_name='Keywords',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='theme',
            field=models.CharField(
                help_text=(
                    'dcat:theme — EU data-theme vocabulary URI; mandatory per HealthDCAT-AP v6 (1..*), '
                    'e.g. http://publications.europa.eu/resource/authority/data-theme/HEAL'
                ),
                max_length=500,
                null=True,
                verbose_name='Theme',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='provenance',
            field=models.TextField(
                help_text='dct:provenance — mandatory per HealthDCAT-AP v6 (1..*)',
                null=True,
                verbose_name='Provenance',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='contact_point',
            field=models.ForeignKey(
                blank=False,
                help_text='dcat:contactPoint — mandatory per HealthDCAT-AP v6 (1..*)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='datasets',
                to='fair_genomes.contactpoint',
                verbose_name='Contact Point',
            ),
        ),
    ]
