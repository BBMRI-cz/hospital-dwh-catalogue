from django.db import migrations, models


DEFAULT_FILTERS = (
    ('keywords', 'Keywords', 10),
    ('custodian', 'Custodian', 20),
    ('health_category', 'Health Category', 30),
    ('source', 'Source', 40),
    ('theme', 'Theme', 50),
)


def seed_default_filters(apps, schema_editor):
    catalogue_filter = apps.get_model('frontend', 'CatalogueFilterDefinition')
    for field_name, label, sort_order in DEFAULT_FILTERS:
        catalogue_filter.objects.update_or_create(
            field_name=field_name,
            defaults={
                'label': label,
                'sort_order': sort_order,
                'is_enabled': True,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='CatalogueFilterDefinition',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'field_name',
                    models.SlugField(
                        help_text='Dataset metadata field used as the catalogue query parameter.',
                        max_length=80,
                        unique=True,
                        verbose_name='Field name',
                    ),
                ),
                (
                    'label',
                    models.CharField(
                        help_text='Human-readable filter group title shown in the sidebar.',
                        max_length=120,
                        verbose_name='Label',
                    ),
                ),
                (
                    'sort_order',
                    models.PositiveIntegerField(
                        default=0,
                        help_text='Lower numbers are shown first.',
                        verbose_name='Sort order',
                    ),
                ),
                (
                    'is_enabled',
                    models.BooleanField(default=True, verbose_name='Enabled'),
                ),
            ],
            options={
                'verbose_name': 'Catalogue Filter Definition',
                'verbose_name_plural': 'Catalogue Filter Definitions',
                'db_table': 'frontend_catalogue_filter_definition',
                'ordering': ['sort_order', 'label', 'field_name'],
            },
        ),
        migrations.RunPython(seed_default_filters, migrations.RunPython.noop),
    ]
