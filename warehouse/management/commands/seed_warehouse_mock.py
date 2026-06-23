"""Seed catalogue-owned warehouse metadata with public mock data."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from warehouse.models import Agent, Catalog, Column, ContactPoint, Dataset, Distribution, Table

DB = 'metadata_db'

LEGISLATION_GDPR_DGA = (
    'http://data.europa.eu/eli/reg/2016/679/oj;'
    'http://data.europa.eu/eli/reg/2022/868/oj'
)
LEGISLATION_DGA = 'http://data.europa.eu/eli/reg/2022/868/oj'
HEALTH_CATEGORY_EHRS = 'http://13.81.34.152:1101/resource/authority/healthcategories/EHRS'
HEALTH_CATEGORY_HRAD = 'http://13.81.34.152:1101/resource/authority/healthcategories/HRAD'
DATA_THEME_HEAL = 'http://publications.europa.eu/resource/authority/data-theme/HEAL'


class Command(BaseCommand):
    help = 'Seed metadata_db with public warehouse metadata sample data.'

    def handle(self, *args, **options):
        if not getattr(settings, 'MOCK_WAREHOUSE_METADATA', False):
            self.stdout.write(
                self.style.WARNING(
                    'MOCK_WAREHOUSE_METADATA is not True - skipping warehouse mock seed.'
                )
            )
            return

        created = 0
        created += self._seed_contact_points()
        created += self._seed_agents()
        created += self._seed_catalogs()
        created += self._seed_datasets()
        created += self._seed_distributions()
        created += self._seed_tables()
        created += self._seed_columns()

        if created:
            self.stdout.write(self.style.SUCCESS(f'warehouse mock seed complete - created: {created}'))
        else:
            self.stdout.write(self.style.SUCCESS('warehouse mock seed complete - all records exist.'))

    def _seed_contact_points(self) -> int:
        rows = [
            (1, 'catalog@hospital.example', 'https://hospital.example/data-catalog/contact'),
            (2, 'labs@hospital.example', None),
            (3, 'hdab@hospital.example', 'https://hospital.example/hdab'),
        ]
        created = 0
        for pk, email, contact_page in rows:
            _, was_created = ContactPoint.objects.using(DB).update_or_create(
                pk=pk,
                defaults={'email': email, 'contact_page': contact_page},
            )
            created += int(was_created)
        return created

    def _seed_agents(self) -> int:
        rows = [
            (
                'AGENT_DWH',
                1,
                'Hospital data warehouse team responsible for metadata stewardship and ETL operations.',
            ),
            ('AGENT_LABS', 2, 'Laboratory informatics team maintaining diagnostic integrations.'),
            (
                'AGENT_HDAB',
                3,
                'Health Data Access Body coordinating dataset access requests and governance.',
            ),
        ]
        created = 0
        for name, contact_point_id, description in rows:
            _, was_created = Agent.objects.using(DB).update_or_create(
                name=name,
                defaults={
                    'contact_point_id': contact_point_id,
                    'description': description,
                },
            )
            created += int(was_created)
        return created

    def _seed_catalogs(self) -> int:
        _, was_created = Catalog.objects.using(DB).update_or_create(
            name='CAT_LM',
            defaults={
                'title': 'Local Metadata Catalogue',
                'description': 'Public mock catalogue for local development and demos.',
                'publisher_id': 'AGENT_DWH',
                'applicable_legislation': LEGISLATION_DGA,
            },
        )
        return int(was_created)

    def _seed_datasets(self) -> int:
        rows = [
            {
                'name': 'DS_PATIENTS',
                'title': 'Patient demographics',
                'version': '1.0.0',
                'description': 'Basic demographic and registration data used in the hospital DWH.',
                'publisher_id': 'AGENT_DWH',
                'keyword': 'patient,demographics,registration',
                'creator_id': 'AGENT_DWH',
                'contact_point_id': 1,
                'provenance': 'Loaded from a mock hospital information system extract.',
                'catalog_id': 'CAT_LM',
                'identifier': 'https://hospital.example/datasets/DS_PATIENTS',
                'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                'applicable_legislation': LEGISLATION_GDPR_DGA,
                'health_category': HEALTH_CATEGORY_EHRS,
                'hdab_id': 'AGENT_HDAB',
                'custodian_id': 'AGENT_DWH',
            },
            {
                'name': 'DS_LABS',
                'title': 'Laboratory results',
                'version': None,
                'description': 'Laboratory measurements with test code, result time, and value.',
                'publisher_id': 'AGENT_LABS',
                'keyword': 'laboratory,diagnostics',
                'creator_id': 'AGENT_LABS',
                'source_id': 'DS_PATIENTS',
                'contact_point_id': 2,
                'provenance': 'Loaded from a mock laboratory information system extract.',
                'catalog_id': 'CAT_LM',
                'identifier': 'https://hospital.example/datasets/DS_LABS',
                'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                'applicable_legislation': 'http://data.europa.eu/eli/reg/2016/679/oj',
                'health_category': HEALTH_CATEGORY_EHRS,
                'hdab_id': 'AGENT_HDAB',
                'custodian_id': None,
            },
            {
                'name': 'DS_CAPACITY',
                'title': 'Hospital capacity summary',
                'version': None,
                'description': 'Aggregated monthly operational indicators without personal data.',
                'publisher_id': 'AGENT_DWH',
                'keyword': 'operations,capacity,admissions',
                'creator_id': 'AGENT_DWH',
                'contact_point_id': 1,
                'provenance': 'Derived from mock monthly operational reporting.',
                'catalog_id': 'CAT_LM',
                'identifier': 'https://hospital.example/datasets/DS_CAPACITY',
                'type': 'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
                'access_rights': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
                'applicable_legislation': LEGISLATION_DGA,
                'health_category': HEALTH_CATEGORY_HRAD,
                'hdab_id': 'AGENT_HDAB',
                'custodian_id': 'AGENT_DWH',
            },
        ]
        created = 0
        for row in rows:
            name = row.pop('name')
            row.setdefault('theme', DATA_THEME_HEAL)
            _, was_created = Dataset.objects.using(DB).update_or_create(name=name, defaults=row)
            created += int(was_created)
        return created

    def _seed_distributions(self) -> int:
        rows = [
            (
                'DIST_PATIENTS_RAW',
                'DS_PATIENTS',
                'Raw patient data',
                'Daily extract before standardization.',
                'http://publications.europa.eu/resource/authority/file-type/PARQUET',
                'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_raw',
                LEGISLATION_GDPR_DGA,
                'raw',
            ),
            (
                'DIST_PATIENTS_CLEAN',
                'DS_PATIENTS',
                'Clean patient layer',
                'Standardized patient data prepared for internal integrations.',
                'http://publications.europa.eu/resource/authority/file-type/PARQUET',
                'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_clean',
                LEGISLATION_GDPR_DGA,
                'clean',
            ),
            (
                'DIST_LABS_RAW',
                'DS_LABS',
                'Raw laboratory data',
                'Laboratory results transferred from the mock LIS.',
                'http://publications.europa.eu/resource/authority/file-type/CSV',
                'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_raw',
                'http://data.europa.eu/eli/reg/2016/679/oj',
                'raw',
            ),
            (
                'DIST_CAPACITY_ANALYTICAL',
                'DS_CAPACITY',
                'Capacity analytical facts',
                'Monthly operational indicators suitable for reporting.',
                'http://publications.europa.eu/resource/authority/file-type/PARQUET',
                'jdbc:postgresql://dwh-db:5432/dwh/analytics.fact_capacity_monthly',
                LEGISLATION_DGA,
                'analytical',
            ),
        ]
        created = 0
        for name, dataset_name_id, title, description, format_uri, access_url, legislation, db_layer in rows:
            _, was_created = Distribution.objects.using(DB).update_or_create(
                name=name,
                defaults={
                    'dataset_name_id': dataset_name_id,
                    'title': title,
                    'description': description,
                    'format': format_uri,
                    'access_url': access_url,
                    'applicable_legislation': legislation,
                    'db_layer': db_layer,
                },
            )
            created += int(was_created)
        return created

    def _seed_tables(self) -> int:
        rows = [
            ('TBL_PAT_RAW', 'DIST_PATIENTS_RAW', 'metadata.patients_raw', 'Patients raw'),
            ('TBL_PAT_CLN', 'DIST_PATIENTS_CLEAN', 'metadata.patients_clean', 'Patients clean'),
            ('TBL_LAB_RAW', 'DIST_LABS_RAW', 'metadata.labs_raw', 'Laboratory results raw'),
            (
                'TBL_CAP_ANA',
                'DIST_CAPACITY_ANALYTICAL',
                'analytics.fact_capacity_monthly',
                'Capacity monthly facts',
            ),
        ]
        created = 0
        for name, distribution_id, url, title in rows:
            _, was_created = Table.objects.using(DB).update_or_create(
                name=name,
                defaults={
                    'distribution_id': distribution_id,
                    'url': url,
                    'title': title,
                    'description': f'Mock physical table {url}.',
                },
            )
            created += int(was_created)
        return created

    def _seed_columns(self) -> int:
        rows = [
            ('COL_PAT_RAW_PATIENT_ID', 'TBL_PAT_RAW', 'Patient ID', 'BIGINT', 1, 'PK'),
            ('COL_PAT_RAW_BIRTH_DATE', 'TBL_PAT_RAW', 'Birth date', 'DATE', 2, None),
            ('COL_PAT_RAW_SEX_CODE', 'TBL_PAT_RAW', 'Sex code', 'VARCHAR', 3, None),
            ('COL_PAT_CLN_PATIENT_KEY', 'TBL_PAT_CLN', 'Patient key', 'BIGINT', 1, 'PK'),
            ('COL_PAT_CLN_ANON_ID', 'TBL_PAT_CLN', 'Pseudonymized ID', 'VARCHAR', 2, 'UK'),
            ('COL_PAT_CLN_AGE_GROUP', 'TBL_PAT_CLN', 'Age group', 'VARCHAR', 3, None),
            ('COL_LAB_RAW_RESULT_ID', 'TBL_LAB_RAW', 'Result ID', 'BIGINT', 1, 'PK'),
            ('COL_LAB_RAW_PATIENT_ID', 'TBL_LAB_RAW', 'Patient ID', 'BIGINT', 2, 'FK'),
            ('COL_LAB_RAW_LOINC_CODE', 'TBL_LAB_RAW', 'LOINC code', 'VARCHAR', 3, None),
            ('COL_LAB_RAW_RESULT_VALUE', 'TBL_LAB_RAW', 'Result value', 'DECIMAL', 4, None),
            ('COL_CAP_ANA_REPORT_MONTH', 'TBL_CAP_ANA', 'Report month', 'DATE', 1, 'PK'),
            ('COL_CAP_ANA_DEPARTMENT_CODE', 'TBL_CAP_ANA', 'Department code', 'VARCHAR', 2, 'PK'),
            ('COL_CAP_ANA_ADMISSIONS', 'TBL_CAP_ANA', 'Admissions count', 'INTEGER', 3, None),
            ('COL_CAP_ANA_AVG_LOS', 'TBL_CAP_ANA', 'Average length of stay', 'DECIMAL', 4, None),
        ]
        created = 0
        for name, table_id, title, datatype, var_order, key_db in rows:
            _, was_created = Column.objects.using(DB).update_or_create(
                name=name,
                defaults={
                    'table_id': table_id,
                    'title': title,
                    'description': f'Mock column {title}.',
                    'datatype': datatype,
                    'var_order': var_order,
                    'key_db': key_db,
                    'type_r': self._r_type_for(datatype),
                    'definition_ddl': f'{title.lower().replace(" ", "_")} {datatype}',
                },
            )
            created += int(was_created)
        return created

    @staticmethod
    def _r_type_for(datatype: str) -> str:
        mapping = {
            'BIGINT': 'integer',
            'INTEGER': 'integer',
            'DECIMAL': 'numeric',
            'DATE': 'Date',
            'VARCHAR': 'character',
        }
        return mapping.get(datatype, 'character')
