"""
Data migration — seed the six original StatDefinition rows.

These correspond to the former hardcoded entries in ``stat_config.py``.
On fresh installs the mock-seed command creates them, but existing
deployments need this migration so the charts keep working after the
switch from stat_config to DB-backed definitions.
"""

from django.db import migrations

SEED = [
    ('sequencing', 'sequencinginstrumentmodel', 'DIST_FG_WES_BAM', 0),
    ('sequencing', 'librarypreparationkit', 'DIST_FG_WES_BAM', 1),
    ('sequencing', 'sequencingtype', 'DIST_FG_WES_BAM', 2),
    ('sample', 'samplematerialtype', 'DIST_FG_WES_BAM', 3),
    ('sample', 'pathologicalstate', 'DIST_FG_WES_BAM', 4),
    ('genomicdata', 'genomebuild', 'DIST_FG_WES_BAM', 5),
]


def forwards(apps, schema_editor):
    StatDefinition = apps.get_model('fair_genomes', 'StatDefinition')
    Distribution = apps.get_model('fair_genomes', 'Distribution')
    db = schema_editor.connection.alias

    # Only seed if the target distribution exists (it won't on a blank DB).
    if not Distribution.objects.using(db).filter(name='DIST_FG_WES_BAM').exists():
        return

    for table, column, dist_name, order in SEED:
        StatDefinition.objects.using(db).get_or_create(
            distribution_id=dist_name,
            molgenis_table=table,
            molgenis_column=column,
            defaults={
                'display_label': '',
                'sort_order': order,
                'is_active': True,
            },
        )


def backwards(apps, schema_editor):
    StatDefinition = apps.get_model('fair_genomes', 'StatDefinition')
    db = schema_editor.connection.alias
    for table, column, dist_name, _ in SEED:
        StatDefinition.objects.using(db).filter(
            distribution_id=dist_name,
            molgenis_table=table,
            molgenis_column=column,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('fair_genomes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
