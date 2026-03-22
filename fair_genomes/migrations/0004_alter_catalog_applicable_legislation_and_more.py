"""
Sync migration: align migration state with current model definitions.

Changes:
- Renames DB column conformed_to → conforms_to on fair_genomes_dataset and
  fair_genomes_distribution tables for existing deployments whose volume was
  created before 0001_initial was updated to use the new column name.
  The rename is guarded by an existence check so it is a no-op on fresh DBs.
- AlterField operations to bring help_text / blank attributes in line with
  the current abstract base model definitions (no DB schema change).
"""

from django.db import migrations, models


def _rename_conformed_to_column(apps, schema_editor):
    """Rename the legacy conformed_to column to conforms_to where it still exists."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        for table in ('fair_genomes_dataset', 'fair_genomes_distribution'):
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'conformed_to'
                """,
                [table],
            )
            if cursor.fetchone():
                cursor.execute(
                    f'ALTER TABLE {table} RENAME COLUMN conformed_to TO conforms_to'  # noqa: S608
                )


class Migration(migrations.Migration):

    dependencies = [
        ('fair_genomes', '0003_dataset_custodian'),
    ]

    operations = [
        migrations.RunPython(
            _rename_conformed_to_column,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='catalog',
            name='applicable_legislation',
            field=models.CharField(
                help_text=(
                    'Legal basis under which this catalog is published — must be a URI/IRI '
                    '(mandatory per HealthDCAT-AP v6, e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
                ),
                max_length=500,
                verbose_name='Applicable Legislation',
            ),
        ),
        migrations.AlterField(
            model_name='contactpoint',
            name='contact_page',
            field=models.CharField(
                blank=True,
                help_text=(
                    'URL of a web page that can be used to reach the contact (vcard:hasURL). '
                    'Must be a URI/IRI. '
                    'At least one of email or contact_page is required.'
                ),
                max_length=500,
                null=True,
                verbose_name='Contact Page',
            ),
        ),
        migrations.AlterField(
            model_name='contactpoint',
            name='email',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Contact e-mail address (vcard:hasEmail). '
                    'Store as plain email (e.g. user@example.org); exported as mailto: URI on RDF output. '
                    'At least one of email or contact_page is required.'
                ),
                max_length=255,
                null=True,
                verbose_name='Email',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='applicable_legislation',
            field=models.CharField(
                help_text=(
                    'dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
                    'e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
                ),
                max_length=500,
                verbose_name='Applicable Legislation',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='health_category',
            field=models.CharField(
                help_text=(
                    'healthdcat:healthCategory — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
                    'e.g. https://healthdataportal.eu/categorisation/Health-care-delivery)'
                ),
                max_length=500,
                verbose_name='Health Category',
            ),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='theme',
            field=models.CharField(
                help_text=(
                    'dcat:theme — must be a URI/IRI from the EU data-theme vocabulary; '
                    'mandatory per HealthDCAT-AP v6 (1..*), '
                    'e.g. http://publications.europa.eu/resource/authority/data-theme/HEAL'
                ),
                max_length=500,
                null=True,
                verbose_name='Theme',
            ),
        ),
        migrations.AlterField(
            model_name='distribution',
            name='applicable_legislation',
            field=models.CharField(
                help_text=(
                    'dct:applicableLegislation — must be a URI/IRI (mandatory per HealthDCAT-AP v6, '
                    'e.g. http://data.europa.eu/eli/reg/2022/868/oj)'
                ),
                max_length=500,
                verbose_name='Applicable Legislation',
            ),
        ),
    ]
