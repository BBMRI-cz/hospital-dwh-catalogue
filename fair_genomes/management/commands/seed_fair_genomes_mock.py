"""
Management command: seed_fair_genomes_mock

Populates the fair_genomes_db with realistic HealthDCAT-AP sample data so that
the application can be evaluated locally without a live FAIR Genomes API.

Activated via MOCK_FAIR_GENOMES=True in the .env file.
Called from docker/entrypoint.sh after migrations have run.

Coverage:
  ContactPoint : email+page | email only | page only
  Agent        : publisher / HDAB / custodian examples with contact_point
  Catalog      : production + staging catalogues with required metadata
  Dataset      : 20 rows — varying optionals + all access_rights /
                 applicable_legislation / health_category combinations
  Distribution : 21 rows — varying format / rights / byte_size combos
                 (no db_layer — that field is warehouse-only)
  StatResult   : 6 mock value distributions (instrument model, library prep kit,
                 sequencing type, sample material type, pathological state, genome build)
"""

import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from fair_genomes.models import (
    Agent,
    Catalog,
    ContactPoint,
    Dataset,
    Distribution,
    StatDefinition,
    StatResult,
)

logger = logging.getLogger(__name__)

DB = 'fair_genomes_db'

LEGISLATION_URIS = {
    'GDPR': 'http://data.europa.eu/eli/reg/2016/679/oj',
    'EHDS': 'http://data.europa.eu/eli/reg/2025/327/oj',
    'NIS2': 'http://data.europa.eu/eli/dir/2022/2555/oj',
    'DGA': 'http://data.europa.eu/eli/reg/2022/868/oj',
}

HEALTH_CATEGORY_BASE = 'http://13.81.34.152:1101/resource/authority/healthcategories/'
HEALTH_CATEGORY_URIS = {
    code: f'{HEALTH_CATEGORY_BASE}{code}'
    for code in (
        'EHCT',
        'HGPD',
        'HPML',
        'EINS',
        'EHRS',
        'HRAD',
        'PGEH',
        'RPDG',
        'DIOH',
        'PHDR',
        'RMMD',
        'WELA',
        'IDHP',
        'MRMR',
        'NRPE',
        'RQSH',
        'EMRD',
    )
}
HEALTH_CATEGORY_URIS.update(
    {
        # Backwards-compatible aliases for older mock rows and UI fixtures.
        'patient_data': HEALTH_CATEGORY_URIS['EHRS'],
        'diagnostic_data': HEALTH_CATEGORY_URIS['EHRS'],
        'medication_data': HEALTH_CATEGORY_URIS['HRAD'],
        'research_data': HEALTH_CATEGORY_URIS['RQSH'],
        'administrative_data': HEALTH_CATEGORY_URIS['HRAD'],
    }
)

FILE_TYPE_BASE = 'http://publications.europa.eu/resource/authority/file-type/'
FILE_TYPE_URIS = {
    code: f'{FILE_TYPE_BASE}{code}'
    for code in (
        'CSV',
        'TSV',
        'JSON',
        'JSON_LD',
        'XML',
        'PARQUET',
        'GZIP',
        'ZIP',
        'OCTET',
    )
}

DATASET_HEALTH_CATEGORY_OVERRIDES = {
    'DS_FG_COHORT': 'HGPD;EINS;RQSH',
    'DS_FG_VARIANTS': 'HGPD',
    'DS_FG_CLINICAL': 'EHRS',
    'DS_FG_BIOBANK': 'EINS',
    'DS_FG_ADMIN': 'HRAD',
    'DS_FG_PHENOTYPES': 'EHRS;RQSH',
    'DS_FG_CONSENT': 'HRAD',
    'DS_FG_SAMPLES': 'EINS',
    'DS_FG_FAMILY_HISTORY': 'EHRS',
    'DS_FG_WES': 'HGPD',
    'DS_FG_RNA_SEQ': 'HPML',
    'DS_FG_PROTEOMICS': 'HPML',
    'DS_FG_METABOLOMICS': 'HPML',
    'DS_FG_MICROBIOME': 'HPML',
    'DS_FG_EPIGENOMICS': 'HGPD',
    'DS_FG_PHARMACOGENOMICS': 'HGPD',
    'DS_FG_RARE_DISEASES': 'HGPD;MRMR',
    'DS_FG_IMAGING_MRI': 'EHRS',
    'DS_FG_SURVIVAL': 'RQSH',
    'DS_FG_TREATMENT': 'EHRS;HRAD',
}


def _is_http_uri(value: str | None) -> bool:
    return bool(value and (value.startswith('http://') or value.startswith('https://')))


def _split_values(value: str | None) -> list[str]:
    return [item.strip() for item in (value or '').split(';') if item.strip()]


def _mapped_uri_list(value: str | None, mapping: dict[str, str]) -> str:
    values: list[str] = []
    for item in _split_values(value):
        mapped = mapping.get(item) or mapping.get(item.upper()) or mapping.get(item.lower())
        if mapped is None and _is_http_uri(item):
            mapped = item
        if mapped and _is_http_uri(mapped):
            values.append(mapped)
    return ';'.join(values)


def _normalise_legislation(value: str | None) -> str:
    return _mapped_uri_list(value, LEGISLATION_URIS)


def _normalise_health_category(value: str | None) -> str:
    return _mapped_uri_list(value, HEALTH_CATEGORY_URIS)


def _normalise_file_type(value: str | None) -> str | None:
    if not value:
        return None
    if _is_http_uri(value):
        return value
    return FILE_TYPE_URIS.get(value.upper())


def _normalise_distribution_rights(value: str | None) -> str | None:
    # dct:rights expects a RightsStatement node; old textual flags are not valid RDF values.
    return value if _is_http_uri(value) else None


def _normalise_dataset_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(defaults)
    normalised['applicable_legislation'] = _normalise_legislation(
        normalised.get('applicable_legislation')
    )
    normalised['health_category'] = _normalise_health_category(normalised.get('health_category'))
    return normalised


def _normalise_distribution_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(defaults)
    normalised['applicable_legislation'] = _normalise_legislation(
        normalised.get('applicable_legislation')
    )
    normalised['format'] = _normalise_file_type(normalised.get('format'))
    normalised['rights'] = _normalise_distribution_rights(normalised.get('rights'))
    return normalised


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
        ]
        cp_objects: list[ContactPoint] = []
        cp_created = 0
        for data in contact_points:
            obj, created = ContactPoint.objects.using(DB).update_or_create(
                email=data['email'],
                contact_page=data['contact_page'],
                defaults={},
            )
            cp_objects.append(obj)
            if created:
                cp_created += 1
        created_counts['ContactPoint'] = cp_created

        cp_both, cp_email_only, cp_page_only = cp_objects

        agent_data: list[dict[str, Any]] = [
            # with email+page contact + description
            {
                'name': 'FG_AGENT_DWH',
                'contact_point': cp_both,
                'description': 'DWH team responsible for FAIR Genomes data management and pipeline.',
            },
            # with email-only contact + description
            {
                'name': 'FG_AGENT_MOLGENIS',
                'contact_point': cp_email_only,
                'description': 'MOLGENIS platform operator providing FAIR Genomes API access.',
            },
            # with page-only contact — used as HDAB; has description
            {
                'name': 'FG_AGENT_HDAB',
                'contact_point': cp_page_only,
                'description': 'Health Data Access Body overseeing access to genomic datasets.',
            },
        ]
        agent_objects: dict[str, Agent] = {}
        ag_created = 0
        for data in agent_data:
            name = data['name']
            obj, created = Agent.objects.using(DB).update_or_create(
                name=name,
                defaults={
                    'contact_point': data['contact_point'],
                    'description': data.get('description'),
                },
            )
            agent_objects[name] = obj
            if created:
                ag_created += 1
        created_counts['Agent'] = ag_created

        Agent.objects.using(DB).filter(name='FG_AGENT_NO_CONTACT').delete()
        ContactPoint.objects.using(DB).filter(
            email__isnull=True, contact_page__isnull=True
        ).delete()

        hdab = agent_objects['FG_AGENT_HDAB']
        agent_dwh = agent_objects['FG_AGENT_DWH']
        agent_molgenis = agent_objects['FG_AGENT_MOLGENIS']

        cat_full, cat_created_full = Catalog.objects.using(DB).update_or_create(
            name='CAT_FAIR_GENOMES',
            defaults={
                'title': 'FAIR Genomes Catalogue',
                'description': (
                    'HealthDCAT-AP catalogue for FAIR Genomes genomic datasets. '
                    'Sourced from the MOLGENIS FAIR Genomes API.'
                ),
                'publisher': agent_dwh,
                'applicable_legislation': _normalise_legislation('GDPR;EHDS'),
            },
        )
        cat_min, cat_created_min = Catalog.objects.using(DB).update_or_create(
            name='CAT_FG_STAGING',
            defaults={
                'title': 'FAIR Genomes Staging Catalogue',
                'description': (
                    'Staging HealthDCAT-AP catalogue used for FAIR Genomes local '
                    'development and export validation.'
                ),
                'publisher': agent_molgenis,
                'applicable_legislation': _normalise_legislation('GDPR;EHDS'),
            },
        )
        created_counts['Catalog'] = int(cat_created_full) + int(cat_created_min)

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
                    'creator': agent_dwh,
                    'contact_point': cp_both,
                    'provenance': 'Data ze sekvenátoru Illumina NovaSeq 6000, validována dle FAIR Genomes.',
                    'catalog': cat_full,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC'
                    ),
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'patient_data',
                    'hdab': hdab,
                    'custodian': agent_dwh,
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
                    'source_id': 'DS_FG_COHORT',
                    'contact_point': cp_email_only,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/RESTRICTED'
                    ),
                    'applicable_legislation': 'GDPR',
                    'health_category': 'diagnostic_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_CLINICAL: source only; PUBLIC; GDPR;EHDS;NIS2; medication_data
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
                    'publisher': agent_molgenis,
                    'contact_point': cp_both,
                    'access_rights': (
                        'http://publications.europa.eu/resource/authority/access-right/PUBLIC'
                    ),
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'medication_data',
                    'hdab': hdab,
                    'custodian': agent_molgenis,
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
                    'hdab': hdab,
                },
            },
            # DS_FG_PHENOTYPES: detailed phenotype ontology; RESTRICTED; GDPR;EHDS; patient_data
            {
                'name': 'DS_FG_PHENOTYPES',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_PHENOTYPES',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Detailní fenotypová data (HPO)',
                    'description': 'Klinické fenotypy kódované pomocí Human Phenotype Ontology (HPO) pro všechny subjekty kohorty.',
                    'keyword': 'fenotyp,HPO,ontologie,klinické znaky',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Kódováno klinickými genetiky z EHR záznamů dle HPO standardu.',
                    'contact_point': cp_both,
                    'catalog': cat_full,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'patient_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_CONSENT: informed consent records; NON_PUBLIC; GDPR;EHDS;NIS2; administrative_data
            {
                'name': 'DS_FG_CONSENT',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_CONSENT',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
                    'title': 'Záznamy informovaného souhlasu',
                    'description': 'Digitalizované záznamy informovaného souhlasu subjektů studie s podmínkami zpracování.',
                    'keyword': 'souhlas,informovaný souhlas,GDPR,podmínky zpracování',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Skenované a strukturované souhlasy z biobankového systému.',
                    'contact_point': cp_email_only,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'administrative_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_SAMPLES: biobank sample metadata; RESTRICTED; EHDS; research_data
            {
                'name': 'DS_FG_SAMPLES',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_SAMPLES',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Biobankové vzorky - metadata',
                    'description': 'Metadata biobankových vzorků: typ tkáně, odběr, uchování, dostupnost a kvalita.',
                    'keyword': 'biobanka,vzorky,tkáně,uchování,kvalita',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Záznamy z LIMS biobankového systému, synchronizovány denně.',
                    'publisher': agent_molgenis,
                    'contact_point': cp_page_only,
                    'catalog': cat_full,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                    'custodian': agent_dwh,
                },
            },
            # DS_FG_FAMILY_HISTORY: family history data; RESTRICTED; GDPR; patient_data
            {
                'name': 'DS_FG_FAMILY_HISTORY',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_FAMILY_HISTORY',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Rodinná anamnéza',
                    'description': 'Strukturovaná rodinná anamnéza zahrnující dědičná onemocnění prvního a druhého stupně.',
                    'keyword': 'rodinná anamnéza,dědičnost,příbuzní,genetická rizika',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Sbíráno v rámci genetické poradny, strukturováno dle HL7 FHIR FamilyMemberHistory.',
                    'contact_point': cp_both,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR',
                    'health_category': 'patient_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_WES: whole exome sequencing; NON_PUBLIC; GDPR;EHDS; research_data
            {
                'name': 'DS_FG_WES',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_WES',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                    'title': 'Celogenomová exomová sekvenace (WES)',
                    'description': 'WES data ve formátu FASTQ/BAM pro diagnostiku vzácných Mendelovských chorob.',
                    'keyword': 'WES,exom,sekvenace,vzácné choroby,Mendelovské',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Sekvenováno na Illumina HiSeq X, pipeline BWA-GATK4.',
                    'publisher': agent_dwh,
                    'catalog': cat_full,
                    'contact_point': cp_both,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_RNA_SEQ: RNA-seq transcriptomics; NON_PUBLIC; GDPR;EHDS;NIS2; research_data
            {
                'name': 'DS_FG_RNA_SEQ',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_RNA_SEQ',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                    'title': 'RNA-seq transkriptomika',
                    'description': 'Bulk a single-cell RNA-seq data z nádorových a kontrolních vzorků kohorty.',
                    'keyword': 'RNA-seq,transkriptomika,single-cell,nádor,genová exprese',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Sekvenováno 10X Genomics Chromium, zpracováno Seurat pipeline.',
                    'contact_point': cp_email_only,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'research_data',
                    'hdab': hdab,
                    'custodian': agent_dwh,
                },
            },
            # DS_FG_PROTEOMICS: proteomics data; RESTRICTED; GDPR;EHDS; research_data
            {
                'name': 'DS_FG_PROTEOMICS',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_PROTEOMICS',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Proteomická data (LC-MS/MS)',
                    'description': 'Kvantitativní proteomika krevní plazmy pomocí LC-MS/MS hmotnostní spektrometrie.',
                    'keyword': 'proteomika,LC-MS,hmotnostní spektrometrie,plazma,proteiny',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Analýza na Orbitrap Eclipse, databáze UniProt, MaxQuant pipeline.',
                    'contact_point': cp_page_only,
                    'catalog': cat_min,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_METABOLOMICS: metabolomics; RESTRICTED; GDPR;EHDS; research_data
            {
                'name': 'DS_FG_METABOLOMICS',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_METABOLOMICS',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Metabolomická data (NMR/MS)',
                    'description': 'Metabolomické profily séra a moče měřené NMR spektroskopií a kapilární elektroforézou.',
                    'keyword': 'metabolomika,NMR,metabolity,sérum,moč',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Měření na Bruker 600 MHz NMR, normalizace PQN metodou.',
                    'contact_point': cp_email_only,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_MICROBIOME: microbiome sequencing; RESTRICTED; GDPR; research_data
            {
                'name': 'DS_FG_MICROBIOME',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_MICROBIOME',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': '16S rRNA mikrobiomová sekvenace',
                    'description': 'Střevní mikrobiom kohorty: 16S rRNA amplikonové sekvenování V3-V4 oblasti.',
                    'keyword': 'mikrobiom,16S rRNA,střevo,mikrobiota,diverzita',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Výstup QIIME2 pipeline, taxonomie dle SILVA 138 databáze.',
                    'contact_point': cp_both,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_EPIGENOMICS: epigenomics; NON_PUBLIC; GDPR;EHDS;NIS2; research_data
            {
                'name': 'DS_FG_EPIGENOMICS',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_EPIGENOMICS',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                    'title': 'Epigenomická data (WGBS)',
                    'description': 'Celogenomová bisulfitová sekvenace (WGBS) pro profily methylace DNA.',
                    'keyword': 'epigenomika,methylace,WGBS,bisulfitová sekvenace,CpG',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Sekvenováno Illumina NovaSeq, pipeline Bismark+DESeq2.',
                    'publisher': agent_dwh,
                    'contact_point': cp_both,
                    'catalog': cat_full,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'research_data',
                    'hdab': hdab,
                    'custodian': agent_molgenis,
                },
            },
            # DS_FG_PHARMACOGENOMICS: pharmacogenomics; RESTRICTED; GDPR;EHDS; medication_data
            {
                'name': 'DS_FG_PHARMACOGENOMICS',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_PHARMACOGENOMICS',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Farmakogenomická data (PGx)',
                    'description': 'Genotypy farmakogenomicky relevantních variant (CYP450, TPMT, DPYD) pro personalizovanou medikaci.',
                    'keyword': 'farmakogenomika,PGx,CYP450,lékové interakce,personalizovaná medicína',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Genotypování SNP polem Affymetrix PharmacoScan, anotace PharmGKB.',
                    'contact_point': cp_email_only,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'medication_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_RARE_DISEASES: rare disease registry; NON_PUBLIC; GDPR;EHDS;NIS2; research_data
            {
                'name': 'DS_FG_RARE_DISEASES',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_RARE_DISEASES',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
                    'title': 'Registr vzácných onemocnění (ORPHA)',
                    'description': 'Klinická a genomická data pacientů s vzácnými onemocněními dle Orphanet klasifikace.',
                    'keyword': 'vzácná onemocnění,Orphanet,ORPHA,registr,genomika',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Kombinace klinických dat a genomických nálezů, manuálně kurátováno.',
                    'publisher': agent_molgenis,
                    'contact_point': cp_both,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'health_category': 'research_data',
                    'hdab': hdab,
                    'custodian': agent_dwh,
                },
            },
            # DS_FG_IMAGING_MRI: MRI metadata; RESTRICTED; GDPR;EHDS; diagnostic_data
            {
                'name': 'DS_FG_IMAGING_MRI',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_IMAGING_MRI',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'MRI zobrazovací metadata (DICOM)',
                    'description': 'DICOM metadata MRI vyšetření mozkových struktur kohorty jako multimodální biomarkery.',
                    'keyword': 'MRI,DICOM,zobrazování,mozek,neuroimaging',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Extrahováno z PACS systému, anonymizováno dle DICOM PS3.15.',
                    'contact_point': cp_page_only,
                    'catalog': cat_full,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'diagnostic_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_SURVIVAL: survival and outcomes; PUBLIC; EHDS; research_data
            {
                'name': 'DS_FG_SURVIVAL',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_SURVIVAL',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
                    'title': 'Přežití a klinické výstupy',
                    'description': 'Anonymizovaná data přežití, remise a relapsů pro epidemiologické studie kohort.',
                    'keyword': 'přežití,výstupy,remise,relaps,epidemiologie',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Agregované anonymizované statistiky, dostupné pro akademické využití.',
                    'contact_point': cp_both,
                    'catalog': cat_min,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
                    'applicable_legislation': 'EHDS',
                    'health_category': 'research_data',
                    'hdab': hdab,
                },
            },
            # DS_FG_TREATMENT: treatment and interventions; RESTRICTED; GDPR;EHDS; medication_data
            {
                'name': 'DS_FG_TREATMENT',
                'defaults': {
                    'identifier': 'https://fairgenomes.hospital.cz/dataset/DS_FG_TREATMENT',
                    'type': 'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
                    'title': 'Léčebné intervence a protokoly',
                    'description': 'Záznamy léčebných protokolů, klinických studií a intervencí pro subjekty kohorty.',
                    'keyword': 'léčba,intervence,protokoly,klinické studie,chemoterapie',
                    'theme': 'http://publications.europa.eu/resource/authority/data-theme/HEAL',
                    'provenance': 'Export z onkologického informačního systému ONCOSYS.',
                    'publisher': agent_molgenis,
                    'contact_point': cp_email_only,
                    'access_rights': 'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
                    'applicable_legislation': 'GDPR;EHDS',
                    'health_category': 'medication_data',
                    'hdab': hdab,
                },
            },
        ]

        ds_created = 0
        dataset_objects: dict[str, Dataset] = {}
        for spec in dataset_specs:
            defaults = dict(spec['defaults'])
            if override := DATASET_HEALTH_CATEGORY_OVERRIDES.get(spec['name']):
                defaults['health_category'] = override
            obj, created = Dataset.objects.using(DB).update_or_create(
                name=spec['name'],
                defaults=_normalise_dataset_defaults(defaults),
            )
            dataset_objects[spec['name']] = obj
            if created:
                ds_created += 1
        created_counts['Dataset'] = ds_created

        # FAIR Genomes distributions have no db_layer (warehouse-only field).
        # Cover format, rights, byte_size, and timestamp combinations.

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
                    'release_date': now,
                    'modification_date': now,
                    'access_url': 'https://fairgenomes.hospital.cz/api/files/cohort.vcf.gz',
                    'applicable_legislation': 'GDPR;EHDS',
                    'licence': 'https://creativecommons.org/licenses/by/4.0/',
                },
            },
            # Partial optional; PARQUET format; restricted; no byte_size; with licence
            {
                'name': 'DIST_FG_COHORT_PARQUET',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_COHORT'],
                    'title': 'Analytický Parquet (kohorta)',
                    'format': 'PARQUET',
                    'rights': 'restricted',
                    'access_url': 'jdbc:postgresql://dwh-db:5432/fair_genomes/cohort_parquet',
                    'applicable_legislation': 'GDPR;EHDS',
                    'licence': 'https://creativecommons.org/licenses/by-nc/4.0/',
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
                    'release_date': now,
                    'access_url': 'https://fairgenomes.hospital.cz/api/phenotypes.jsonld',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                    'licence': 'https://creativecommons.org/licenses/by-nc-nd/4.0/',
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
            # DIST_FG_ADMIN_CSV: data access administration export
            {
                'name': 'DIST_FG_ADMIN_CSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_ADMIN'],
                    'title': 'Administrativní záznamy přístupů (CSV)',
                    'description': 'Auditní export administrace žádostí a přístupových rozhodnutí.',
                    'format': 'CSV',
                    'byte_size': 2097152,
                    'access_url': 'https://fairgenomes.hospital.cz/api/admin/access-audit.csv',
                    'applicable_legislation': 'GDPR',
                    'licence': 'https://creativecommons.org/licenses/by-nc/4.0/',
                },
            },
            # DIST_FG_PHENOTYPES_JSON: HPO JSON-LD export
            {
                'name': 'DIST_FG_PHENOTYPES_JSON',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_PHENOTYPES'],
                    'title': 'HPO fenotypy ve formátu JSON-LD',
                    'format': 'JSON',
                    'conforms_to': 'https://hpo.jax.org/app/',
                    'byte_size': 52428800,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/phenotypes/hpo.jsonld',
                    'applicable_legislation': 'GDPR;EHDS',
                    'licence': 'https://hpo.jax.org/app/license',
                },
            },
            # DIST_FG_CONSENT_CSV: consent status export
            {
                'name': 'DIST_FG_CONSENT_CSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_CONSENT'],
                    'title': 'Záznamy souhlasu (CSV export)',
                    'format': 'CSV',
                    'rights': 'internal',
                    'access_url': 'https://fairgenomes.hospital.cz/api/consent/export.csv',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                },
            },
            # DIST_FG_SAMPLES_JSON: sample catalogue JSON
            {
                'name': 'DIST_FG_SAMPLES_JSON',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_SAMPLES'],
                    'title': 'Katalog vzorků (JSON)',
                    'format': 'JSON',
                    'conforms_to': 'https://fairgenomes.org/sample-schema/v1',
                    'byte_size': 10485760,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/samples/catalogue.json',
                    'applicable_legislation': 'EHDS',
                    'licence': 'https://creativecommons.org/licenses/by/4.0/',
                },
            },
            # DIST_FG_FAMILY_HISTORY_TSV
            {
                'name': 'DIST_FG_FAMILY_HISTORY_TSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_FAMILY_HISTORY'],
                    'title': 'Rodinná anamnéza (TSV)',
                    'format': 'TSV',
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/family/history.tsv',
                    'applicable_legislation': 'GDPR',
                },
            },
            # DIST_FG_WES_BAM: aligned BAM files
            {
                'name': 'DIST_FG_WES_BAM',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_WES'],
                    'title': 'WES sekvenace — zarovnané BAM soubory',
                    'format': 'BAM',
                    'conforms_to': 'https://samtools.github.io/hts-specs/SAMv1.pdf',
                    'byte_size': 107374182400,
                    'rights': 'internal',
                    'access_url': 'https://fairgenomes.hospital.cz/api/files/wes_bam',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
            # DIST_FG_RNA_SEQ_FASTQ: raw FASTQ files
            {
                'name': 'DIST_FG_RNA_SEQ_FASTQ',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_RNA_SEQ'],
                    'title': 'RNA-seq surová FASTQ data',
                    'format': 'FASTQ',
                    'byte_size': 53687091200,
                    'rights': 'internal',
                    'access_url': 'https://fairgenomes.hospital.cz/api/files/rnaseq_fastq',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                },
            },
            # DIST_FG_PROTEOMICS_TSV: MaxQuant output TSV
            {
                'name': 'DIST_FG_PROTEOMICS_TSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_PROTEOMICS'],
                    'title': 'Proteomická kvantifikace (TSV)',
                    'format': 'TSV',
                    'conforms_to': 'https://www.uniprot.org/',
                    'byte_size': 209715200,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/proteomics/maxquant.tsv',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
            # DIST_FG_METABOLOMICS_CSV: NMR spectral data CSV
            {
                'name': 'DIST_FG_METABOLOMICS_CSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_METABOLOMICS'],
                    'title': 'Metabolomická data (CSV)',
                    'format': 'CSV',
                    'byte_size': 104857600,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/metabolomics/nmr.csv',
                    'applicable_legislation': 'GDPR;EHDS',
                    'licence': 'https://creativecommons.org/licenses/by-nc/4.0/',
                },
            },
            # DIST_FG_MICROBIOME_BIOM: QIIME2 BIOM table
            {
                'name': 'DIST_FG_MICROBIOME_BIOM',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_MICROBIOME'],
                    'title': 'Mikrobiomová BIOM tabulka',
                    'format': 'BIOM',
                    'conforms_to': 'https://biom-format.org/',
                    'byte_size': 31457280,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/microbiome/otu_table.biom',
                    'applicable_legislation': 'GDPR',
                },
            },
            # DIST_FG_EPIGENOMICS_BEDGRAPH: methylation BedGraph
            {
                'name': 'DIST_FG_EPIGENOMICS_BEDGRAPH',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_EPIGENOMICS'],
                    'title': 'Methylační profily (BedGraph)',
                    'format': 'BEDGRAPH',
                    'conforms_to': 'https://genome.ucsc.edu/goldenPath/help/bedgraph.html',
                    'byte_size': 21474836480,
                    'rights': 'internal',
                    'access_url': 'https://fairgenomes.hospital.cz/api/epigenomics/methylation.bedgraph',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                },
            },
            # DIST_FG_PHARMACOGENOMICS_VCF: PGx annotated VCF
            {
                'name': 'DIST_FG_PHARMACOGENOMICS_VCF',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_PHARMACOGENOMICS'],
                    'title': 'Farmakogenomické varianty (VCF)',
                    'format': 'VCF',
                    'conforms_to': 'https://cpicpgx.org/guidelines/',
                    'byte_size': 524288000,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/pharmacogenomics/pgx_variants.vcf',
                    'applicable_legislation': 'GDPR;EHDS',
                    'licence': 'https://creativecommons.org/licenses/by/4.0/',
                },
            },
            # DIST_FG_RARE_DISEASES_JSON: Orphanet JSON-LD
            {
                'name': 'DIST_FG_RARE_DISEASES_JSON',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_RARE_DISEASES'],
                    'title': 'Vzácná onemocnění (JSON-LD)',
                    'format': 'JSON',
                    'conforms_to': 'https://www.orphadata.com/ordo/',
                    'byte_size': 20971520,
                    'rights': 'internal',
                    'access_url': 'https://fairgenomes.hospital.cz/api/rare-diseases/ordo.jsonld',
                    'applicable_legislation': 'GDPR;EHDS;NIS2',
                },
            },
            # DIST_FG_IMAGING_MRI_PARQUET: MRI DICOM metadata PARQUET
            {
                'name': 'DIST_FG_IMAGING_MRI_PARQUET',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_IMAGING_MRI'],
                    'title': 'MRI DICOM metadata (Parquet)',
                    'format': 'PARQUET',
                    'conforms_to': 'https://dicom.nema.org/medical/dicom/current/output/html/part03.html',
                    'byte_size': 2684354560,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/imaging/mri_metadata.parquet',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
            # DIST_FG_SURVIVAL_CSV: anonymised survival data CSV
            {
                'name': 'DIST_FG_SURVIVAL_CSV',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_SURVIVAL'],
                    'title': 'Anonymizovaná data přežití (CSV)',
                    'format': 'CSV',
                    'byte_size': 5242880,
                    'rights': 'public',
                    'access_url': 'https://fairgenomes.hospital.cz/api/survival/cohort_survival.csv',
                    'applicable_legislation': 'EHDS',
                    'licence': 'https://creativecommons.org/licenses/by/4.0/',
                },
            },
            # DIST_FG_TREATMENT_JSON: treatment protocol JSON
            {
                'name': 'DIST_FG_TREATMENT_JSON',
                'defaults': {
                    'dataset_name': dataset_objects['DS_FG_TREATMENT'],
                    'title': 'Léčebné protokoly (JSON)',
                    'format': 'JSON',
                    'byte_size': 41943040,
                    'rights': 'restricted',
                    'access_url': 'https://fairgenomes.hospital.cz/api/treatment/protocols.json',
                    'applicable_legislation': 'GDPR;EHDS',
                },
            },
        ]

        dist_created = 0
        dist_objects: dict[str, Distribution] = {}
        for spec in distribution_specs:
            obj, created = Distribution.objects.using(DB).update_or_create(
                name=spec['name'],
                defaults=_normalise_distribution_defaults(spec['defaults']),
            )
            dist_objects[spec['name']] = obj
            if created:
                dist_created += 1
        created_counts['Distribution'] = dist_created

        # Seed a mock value distribution that _sync_stats() would write after
        # a real sync.  Uses plausible mock values so the application can be
        # evaluated without a live MOLGENIS connection.
        from django.utils import timezone as tz

        stat_specs: list[dict] = [
            {
                'table_name': 'sequencing',
                'column_name': 'sequencinginstrumentmodel',
                'defaults': {
                    'distribution': {
                        'MiSeq': 87,
                        'NovaSeq 6000': 42,
                        'HiSeq X': 15,
                        'NextSeq 550': 8,
                    },
                    'last_synced': tz.now(),
                },
            },
            {
                'table_name': 'sequencing',
                'column_name': 'librarypreparationkit',
                'defaults': {
                    'distribution': {
                        'Twist Human Core Exome': 68,
                        'Agilent SureSelect XT': 41,
                        'Illumina TruSeq DNA': 19,
                        'KAPA HyperPrep': 14,
                        'NEBNext Ultra II': 10,
                    },
                    'last_synced': tz.now(),
                },
            },
            {
                'table_name': 'sequencing',
                'column_name': 'sequencingtype',
                'defaults': {
                    'distribution': {
                        'WES': 109,
                        'WGS': 27,
                        'RNA-seq': 15,
                        'Panel': 1,
                    },
                    'last_synced': tz.now(),
                },
            },
            {
                'table_name': 'sample',
                'column_name': 'samplematerialtype',
                'defaults': {
                    'distribution': {
                        'Peripheral blood': 93,
                        'FFPE tissue': 34,
                        'Fresh frozen tissue': 18,
                        'Saliva': 7,
                    },
                    'last_synced': tz.now(),
                },
            },
            {
                'table_name': 'sample',
                'column_name': 'pathologicalstate',
                'defaults': {
                    'distribution': {
                        'Tumor': 71,
                        'Normal': 63,
                        'Germline': 18,
                    },
                    'last_synced': tz.now(),
                },
            },
            {
                'table_name': 'genomicdata',
                'column_name': 'genomebuild',
                'defaults': {
                    'distribution': {
                        'GRCh38': 118,
                        'GRCh37': 34,
                    },
                    'last_synced': tz.now(),
                },
            },
        ]

        stat_created = 0
        for spec in stat_specs:
            _obj, created = StatResult.objects.using(DB).update_or_create(
                table_name=spec['table_name'],
                column_name=spec['column_name'],
                defaults=spec['defaults'],
            )
            if created:
                stat_created += 1
        created_counts['StatResult'] = stat_created

        # Each StatResult must have a corresponding StatDefinition that links
        # the MOLGENIS table/column pair to the distribution whose detail page
        # shows the chart.
        wes_bam_dist = dist_objects.get('DIST_FG_WES_BAM')
        sd_created = 0
        if wes_bam_dist:
            for idx, spec in enumerate(stat_specs):
                _sd, created = StatDefinition.objects.using(DB).get_or_create(
                    distribution=wes_bam_dist,
                    molgenis_table=spec['table_name'],
                    molgenis_column=spec['column_name'],
                    defaults={
                        'sort_order': idx,
                        'is_active': True,
                    },
                )
                if created:
                    sd_created += 1
        created_counts['StatDefinition'] = sd_created

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
