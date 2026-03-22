"""
Management command: seed_fair_genomes_mock

Populates the fair_genomes_db with realistic HealthDCAT-AP sample data so that
the application can be evaluated locally without a live FAIR Genomes API.

Activated via MOCK_FAIR_GENOMES=True in the .env file.
Called from docker/entrypoint.sh after migrations have run.

Coverage:
  ContactPoint : email+page | email only | page only | neither
  Agent        : with / without contact_point
  Catalog      : full fields + minimal fields
  Dataset      : 5 rows —  varying optionals + all access_rights /
                 applicable_legislation / health_category combinations
  Distribution : 5 rows — varying format / rights / byte_size combos
                 (no db_layer — that field is warehouse-only)
"""

import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from fair_genomes.models import Agent, Catalog, ContactPoint, Dataset, Distribution

logger = logging.getLogger(__name__)

DB = 'fair_genomes_db'


class Command(BaseCommand):
    help = 'Seed fair_genomes_db with mock HealthDCAT-AP sample data (MOCK_FAIR_GENOMES=True).'

    def handle(self, *args: Any, **options: Any) -> None:
        if not getattr(settings, 'MOCK_FAIR_GENOMES', False):
            self.stdout.write(
                self.style.WARNING(
                    'MOCK_FAIR_GENOMES is not True — skipping fair_genomes mock seed.'
                )
            )
            return

        self.stdout.write('Seeding fair_genomes_db with mock data …')
        created_counts: dict[str, int] = {}

        # ── ContactPoints ──────────────────────────────────────────────────
        contact_points = [
            # email + page
            {
                'email': 'fg-data@hospital.cz',
                'contact_page': 'https://hospital.cz/fairgenomes',
            },
            # email only
            {'email': 'fg-admin@hospital.cz', 'contact_page': None},
            # page only
            {'email': None, 'contact_page': 'https://hospital.cz/fairgenomes/contact'},
            # neither
            {'email': None, 'contact_page': None},
        ]
        cp_objects: list[ContactPoint] = []
        cp_created = 0
        for data in contact_points:
            obj, created = ContactPoint.objects.using(DB).get_or_create(**data)
            cp_objects.append(obj)
            if created:
                cp_created += 1
        created_counts['ContactPoint'] = cp_created

        cp_both, cp_email_only, cp_page_only, cp_none = cp_objects

        # ── Agents ─────────────────────────────────────────────────────────
        agent_data = [
            # with email+page contact
            {
                'name': 'FG_AGENT_DWH',
                'contact_point': cp_both,
            },
            # with email-only contact
            {
                'name': 'FG_AGENT_MOLGENIS',
                'contact_point': cp_email_only,
            },
            # with page-only contact — used as HDAB
            {
                'name': 'FG_AGENT_HDAB',
                'contact_point': cp_page_only,
            },
            # no contact at all
            {'name': 'FG_AGENT_NO_CONTACT', 'contact_point': None},
        ]
        agent_objects: dict[str, Agent] = {}
        ag_created = 0
        for data in agent_data:
            name = data['name']
            obj, created = Agent.objects.using(DB).get_or_create(
                name=name,
                defaults={
                    'contact_point': data['contact_point'],
                },
            )
            agent_objects[name] = obj
            if created:
                ag_created += 1
        created_counts['Agent'] = ag_created

        hdab = agent_objects['FG_AGENT_HDAB']
        agent_dwh = agent_objects['FG_AGENT_DWH']
        agent_molgenis = agent_objects['FG_AGENT_MOLGENIS']

        # ── Catalogs ───────────────────────────────────────────────────────
        cat_full, cat_created_full = Catalog.objects.using(DB).get_or_create(
            name='CAT_FAIR_GENOMES',
            defaults={
                'title': 'FAIR Genomes Catalogue',
                'description': (
                    'HealthDCAT-AP catalogue for FAIR Genomes genomic datasets. '
                    'Sourced from the MOLGENIS FAIR Genomes API.'
                ),
                'publisher': agent_dwh,
                'applicable_legislation': 'GDPR;EHDS',
            },
        )
        # Minimal catalog: no title/description/publisher — only mandatory field
        cat_min, cat_created_min = Catalog.objects.using(DB).get_or_create(
            name='CAT_FG_STAGING',
            defaults={'applicable_legislation': 'GDPR'},
        )
        created_counts['Catalog'] = int(cat_created_full) + int(cat_created_min)

        # ── Datasets ──────────────────────────────────────────────────────
        now = timezone.now()

        dataset_specs: list[dict[str, Any]] = [
            # DS_FG_COHORT: NON_PUBLIC; GDPR;EHDS; patient_data
            {
                'name': 'DS_FG_COHORT',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_COHORT',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                    'title': 'Genomická kohorta pacientů',
                    'version': '2.0.0',
                    'description': (
                        'Kohortová studie genomických dat pacientů: WGS, RNA-seq, '
                        'klinické fenotypy a biobankovací metadata.'
                    ),
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'publisher': agent_dwh,
                    'conforms_to': 'https://fairgenomes.org/spec/v2',
                    'issued': now,
                    'modified': now,
                    'keyword': 'genomika,WGS,RNA-seq,kohorta,biobanka',
                    'source': 'https://fairgenomes.hospital.cz/api/cohort',
                    'creator': 'Genomický tým; IT oddělení',
                    'contact_point': cp_both,
                    'rights_holder': 'Nemocnice a.s.',
                    'provenance': 'Data ze sekvenátoru Illumina NovaSeq 6000, validována dle FAIR Genomes.',
                    'catalog': cat_full,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC'
                    ),
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'patient_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_VARIANTS: partial optionals; RESTRICTED; GDPR only; diagnostic_data
            {
                'name': 'DS_FG_VARIANTS',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_VARIANTS',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Varianty genomické sekvence',
                    'description': 'VCF soubory s variantami identifikovanými v kohortě (SNP, InDel, CNV).',
                    'keyword': 'VCF,SNP,InDel,CNV,varianty',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Variant calling pipeline GATK4 na sekvenačních datech kohorty.',
                    'contact_point': cp_email_only,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/RESTRICTED'
                    ),
                    'applicable_legislation': 'GDPR',
                    'health_category': 'diagnostic_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_CLINICAL: source + rights_holder only; PUBLIC; GDPR;EHDS;NIS2; medication_data
            {
                'name': 'DS_FG_CLINICAL',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_CLINICAL',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
                    'title': 'Klinická fenotypová data',
                    'description': 'Fenotypová a klinická data z elektronické zdravotní dokumentace.',
                    'keyword': 'fenotyp,klinika,EHR,diagnóza',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Export z nemocničního informačního systému, pseudonymizován před předáním.',
                    'source': 'https://fairgenomes.hospital.cz/api/phenotypes',
                    'rights_holder': 'Genomická biobanková komise',
                    'publisher': agent_molgenis,
                    'contact_point': cp_both,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                    ),
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'medication_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_BIOBANK: catalog=staging; research_data; EHDS only; minimal optional
            {
                'name': 'DS_FG_BIOBANK',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_BIOBANK',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Biobanková metadata',
                    'description': 'Metadata biobankových vzorků v nemocniční biorepozitáři.',
                    'keyword': 'biobanka,vzorky,tkáně',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Záznamy z biobankového systému LIMS.',
                    'contact_point': cp_page_only,
                    'catalog': cat_min,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/RESTRICTED'
                    ),
                    'applicable_legislation': 'EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_ADMIN: administrative_data; GDPR; NON_PUBLIC; minimal optional
            {
                'name': 'DS_FG_ADMIN',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_ADMIN',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
                    'title': 'Administrativní data',
                    'description': 'Administrativní záznamy o přístupu k datům a žádostech.',
                    'keyword': 'administrace,přístup,žádosti',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Generováno ze systému správy žádostí HDAB.',
                    'contact_point': cp_email_only,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC'
                    ),
                    'applicable_legislation': 'GDPR',
                    'health_category': 'administrative_data',
                    'hdab': agent_objects['FG_AGENT_NO_CONTACT'],
                },
            },
        ]

        ds_created = 0
        dataset_objects: dict[str, Dataset] = {}
        for spec in dataset_specs:
            obj, created = Dataset.objects.using(DB).get_or_create(
                name=spec['name'],
                defaults=spec['defaults'],
            )
            dataset_objects[spec['name']] = obj
            if created:
                ds_created += 1
        created_counts['Dataset'] = ds_created

        # ── Distributions ─────────────────────────────────────────────────
        # Fair Genomes distributions have no db_layer (warehouse-only field).
        # Cover: format × rights × byte_size × timestamps

        distribution_specs: list[dict[str, Any]] = [
            # All optional filled; VCF format; internal; large byte_size
            {
                'name': 'DIST_FG_COHORT_VCF',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_COHORT'],
                    'title': 'Distribucia VCF (kohorta)',
                    'description': 'Komprimované VCF soubory pro celou kohortu.',
                    'format': 'VCF',
                    'conforms_to': 'https://samtools.github.io/hts-specs/VCFv4.3.pdf',
                    'byte_size': 10737418240,  # 10 GB
                    'rights': 'internal',
                    'issued': now,
                    'modified': now,
                    'access_url': 'https://fairgenomes.hospital.cz/api/files/cohort.vcf.gz',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
            # Partial optional; PARQUET format; restricted; no byte_size
            {
                'name': 'DIST_FG_COHORT_PARQUET',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_COHORT'],
                    'title': 'Analytický Parquet (kohorta)',
                    'format': 'PARQUET',
                    'rights': 'restricted',
                    'access_url': 'jdbc:postgresql://dwh-db:5432/fair_genomes/cohort_parquet',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
            # Minimal mandatory only; no optional; TSV format; public
            {
                'name': 'DIST_FG_VARIANTS_TSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_VARIANTS'],
                    'format': 'TSV',
                    'rights': 'public',
                    'access_url': 'https://fairgenomes.hospital.cz/api/files/variants.tsv',
                    'applicable_legislation': 'GDPR',
                },
            },
            # JSON format; no rights; byte_size set; issued only (no modified)
            {
                'name': 'DIST_FG_CLINICAL_JSON',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_CLINICAL'],
                    'title': 'Klinická data ve formátu JSON-LD',
                    'description': 'JSON-LD export klinických fenotypů dle FAIR Genomes schématu.',
                    'format': 'JSON',
                    'byte_size': 524288000,  # 500 MB
                    'issued': now,
                    'access_url': 'https://fairgenomes.hospital.cz/api/phenotypes.jsonld',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                },
            },
            # No optional fields at all; NULL format; NULL rights; NULL byte_size
            {
                'name': 'DIST_FG_BIOBANK_RAW',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_BIOBANK'],
                    'access_url': 'https://fairgenomes.hospital.cz/api/biobank/raw',
                    'applicable_legislation': 'EHDS',
                },
            },
        ]

        dist_created = 0
        for spec in distribution_specs:
            _obj, created = Distribution.objects.using(DB).get_or_create(
                name=spec['name'],
                defaults=spec['defaults'],
            )
            if created:
                dist_created += 1
        created_counts['Distribution'] = dist_created

        # ── Summary ────────────────────────────────────────────────────────
        total = sum(created_counts.values())
        summary = ', '.join(f'{k}: {v}' for k, v in created_counts.items())
        if total:
            self.stdout.write(
                self.style.SUCCESS(f'fair_genomes mock seed complete — created: {summary}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('fair_genomes mock seed complete — all records already exist.')
            )
