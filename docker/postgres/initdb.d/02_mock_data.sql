-- ============================================================
-- Mock warehouse data — Local Metadata HealthDCAT-AP (lm_* tables)
-- ============================================================
-- Runs once on first Postgres container start via initdb.d/.
-- The sample is intentionally small and coherent:
--   * 3 datasets
--   * 4 distributions
--   * 4 physical tables
--   * a handful of realistic columns
--
-- Design goals:
--   * satisfy the actually required warehouse relationships
--   * keep contact points and agents semantically valid
--   * populate some optional fields, but not every optional field everywhere
--   * provide enough variety for the UI to show ready/raw/unavailable states
-- ============================================================

-- ── ContactPoints ────────────────────────────────────────────
INSERT INTO metadata."lm_contact_point" (id, email, contact_page)
OVERRIDING SYSTEM VALUE VALUES
(1, 'catalog@hospital.cz', 'https://hospital.cz/data-catalog/contact'),
(2, 'labs@hospital.cz', NULL),
(3, 'hdab@hospital.cz', 'https://hospital.cz/hdab');

SELECT setval(pg_get_serial_sequence('metadata."lm_contact_point"', 'id'), 3);

-- ── Agents ───────────────────────────────────────────────────
INSERT INTO metadata."lm_agent" (name, contact_point_id, description) VALUES
(
    'AGENT_DWH',
    1,
    'Hospital data warehouse team responsible for metadata stewardship and ETL operations.'
),
(
    'AGENT_LABS',
    2,
    'Laboratory informatics team maintaining diagnostic result integrations.'
),
(
    'AGENT_HDAB',
    3,
    'Health Data Access Body coordinating dataset access requests and governance.'
);

-- ── Catalog ──────────────────────────────────────────────────
INSERT INTO metadata."lm_catalog" (
    name, title, description, publisher_id, applicable_legislation
) VALUES (
    'CAT_LM',
    'Katalog lokálních metadat',
    'Ukázkový katalog nemocničního datového skladu se třemi menšími datasety pro lokální vývoj a testování.',
    'AGENT_DWH',
    'http://data.europa.eu/eli/reg/2022/868/oj'
);

-- ── Datasets ─────────────────────────────────────────────────
-- Each dataset includes the fields required by the warehouse model layer:
-- title, description, identifier, type, theme, keyword, provenance,
-- contact_point_id, access_rights, applicable_legislation, health_category, hdab_id.

INSERT INTO metadata."lm_dataset" (
    name,
    title,
    version,
    description,
    theme,
    publisher_id,
    conforms_to,
    issued,
    modified,
    keyword,
    creator,
    contact_point_id,
    provenance,
    catalog_id,
    identifier,
    type,
    access_rights,
    applicable_legislation,
    health_category,
    hdab_id,
    custodian_id
) VALUES (
    'DS_PATIENTS',
    'Demografická data pacientů',
    '1.2.0',
    'Základní demografická a registrační data pacientů používaná napříč nemocničním datovým skladem.',
    'http://publications.europa.eu/resource/authority/data-theme/HEAL',
    'AGENT_DWH',
    'https://healthdcat-ap.eu/spec/v6',
    '2024-01-15 00:00:00+01',
    '2026-03-10 00:00:00+01',
    'patient,demographics,registration',
    'AGENT_DWH',
    1,
    'Data jsou přebírána z nemocničního informačního systému v denních dávkách a následně pseudonymizována.',
    'CAT_LM',
    'https://hospital.cz/datasets/DS_PATIENTS',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'http://data.europa.eu/eli/reg/2016/679/oj;http://data.europa.eu/eli/reg/2022/868/oj',
    'patient_data',
    'AGENT_HDAB',
    'AGENT_DWH'
);

INSERT INTO metadata."lm_dataset" (
    name,
    title,
    description,
    theme,
    publisher_id,
    keyword,
    source,
    contact_point_id,
    provenance,
    catalog_id,
    identifier,
    type,
    access_rights,
    applicable_legislation,
    health_category,
    hdab_id
) VALUES (
    'DS_LABS',
    'Laboratorní výsledky',
    'Výsledky laboratorních vyšetření včetně identifikace testu, času výsledku a naměřené hodnoty.',
    'http://publications.europa.eu/resource/authority/data-theme/HEAL',
    'AGENT_LABS',
    'laboratory,diagnostics,loinc',
    'DS_PATIENTS',
    2,
    'Primární data vznikají v laboratorním informačním systému a do skladu jsou načítána průběžně během dne.',
    'CAT_LM',
    'https://hospital.cz/datasets/DS_LABS',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'http://data.europa.eu/eli/reg/2016/679/oj',
    'diagnostic_data',
    'AGENT_HDAB'
);

INSERT INTO metadata."lm_dataset" (
    name,
    title,
    description,
    theme,
    publisher_id,
    keyword,
    contact_point_id,
    provenance,
    catalog_id,
    identifier,
    type,
    access_rights,
    applicable_legislation,
    health_category,
    hdab_id
) VALUES (
    'DS_CAPACITY',
    'Souhrn kapacit a hospitalizačního provozu',
    'Agregované měsíční ukazatele lůžkové kapacity, příjmů a průměrné délky hospitalizace bez osobních údajů.',
    'http://publications.europa.eu/resource/authority/data-theme/HEAL',
    'AGENT_DWH',
    'operations,capacity,admissions',
    1,
    'Dataset vzniká měsíční agregací provozních ukazatelů z interního reportingu a neobsahuje identifikovatelné pacienty.',
    'CAT_LM',
    'https://hospital.cz/datasets/DS_CAPACITY',
    'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
    'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
    'http://data.europa.eu/eli/reg/2022/868/oj',
    'administrative_data',
    'AGENT_HDAB'
);

-- ── Distributions ────────────────────────────────────────────
INSERT INTO metadata."lm_distribution" (
    name,
    dataset_name,
    title,
    description,
    format,
    conforms_to,
    byte_size,
    rights,
    release_date,
    modification_date,
    access_url,
    applicable_legislation,
    licence,
    db_layer
) VALUES (
    'DIST_PATIENTS_RAW',
    'DS_PATIENTS',
    'Surová data pacientů',
    'Denní extrakt pacientských registrací před standardizačními transformacemi.',
    'PARQUET',
    'https://healthdcat-ap.eu/spec/v6',
    157286400,
    'internal',
    '2024-01-15 00:00:00+01',
    '2026-03-10 00:00:00+01',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_raw',
    'http://data.europa.eu/eli/reg/2016/679/oj;http://data.europa.eu/eli/reg/2022/868/oj',
    'https://creativecommons.org/licenses/by-nc/4.0/',
    'raw'
);

INSERT INTO metadata."lm_distribution" (
    name,
    dataset_name,
    title,
    format,
    rights,
    access_url,
    applicable_legislation,
    db_layer
) VALUES (
    'DIST_PATIENTS_CLEAN',
    'DS_PATIENTS',
    'Čistá vrstva pacientů',
    'DELTA',
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_clean',
    'http://data.europa.eu/eli/reg/2016/679/oj;http://data.europa.eu/eli/reg/2022/868/oj',
    'clean'
);

INSERT INTO metadata."lm_distribution" (
    name,
    dataset_name,
    title,
    format,
    rights,
    access_url,
    applicable_legislation,
    db_layer
) VALUES (
    'DIST_LABS_RAW',
    'DS_LABS',
    'Surová laboratorní data',
    'CSV',
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_raw',
    'http://data.europa.eu/eli/reg/2016/679/oj',
    'raw'
);

INSERT INTO metadata."lm_distribution" (
    name,
    dataset_name,
    title,
    description,
    format,
    rights,
    access_url,
    applicable_legislation,
    licence,
    db_layer
) VALUES (
    'DIST_CAPACITY_ANALYTICAL',
    'DS_CAPACITY',
    'Agregovaná kapacitní fakta',
    'Měsíční analytická vrstva s agregovanými provozními ukazateli vhodná pro interní i veřejné reporty.',
    'PARQUET',
    'public',
    'jdbc:postgresql://dwh-db:5432/dwh/analytics.fact_capacity_monthly',
    'http://data.europa.eu/eli/reg/2022/868/oj',
    'https://creativecommons.org/licenses/by/4.0/',
    'analytical'
);

-- ── Tables ───────────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
(
    'TBL_PAT_RAW',
    'DIST_PATIENTS_RAW',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_raw',
    'Pacienti (surová vrstva)',
    'Surová data pacientů převzatá přímo ze zdrojového nemocničního systému.'
),
(
    'TBL_PAT_CLN',
    'DIST_PATIENTS_CLEAN',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_clean',
    'Pacienti (čistá vrstva)',
    'Vyčištěná a standardizovaná pacientská data připravená pro další integrace.'
),
(
    'TBL_LAB_RAW',
    'DIST_LABS_RAW',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_raw',
    'Laboratorní výsledky (surová vrstva)',
    'Surové laboratorní výsledky přenesené z LIS bez další agregace.'
),
(
    'TBL_CAP_ANA',
    'DIST_CAPACITY_ANALYTICAL',
    'jdbc:postgresql://dwh-db:5432/dwh/analytics.fact_capacity_monthly',
    'Kapacita a hospitalizace (analytická vrstva)',
    'Agregovaná tabulka měsíčních provozních ukazatelů bez osobních údajů.'
);

-- ── Columns ──────────────────────────────────────────────────
INSERT INTO metadata."lm_column" (
    name,
    table_name,
    title,
    description,
    datatype,
    property_url,
    var_order,
    key_db,
    type_r,
    definition_ddl,
    definition_pk_pom1,
    definition_pk_pom2,
    definition_pk
) VALUES
(
    'COL_PAT_RAW_PATIENT_ID',
    'TBL_PAT_RAW',
    'ID pacienta',
    'Interní identifikátor pacienta převzatý ze zdrojového systému.',
    'BIGINT',
    'http://snomed.info/sct/116154003',
    1,
    'PK',
    'integer',
    'patient_id BIGINT NOT NULL PRIMARY KEY',
    NULL,
    NULL,
    'PRIMARY KEY (patient_id)'
),
(
    'COL_PAT_RAW_BIRTH_DATE',
    'TBL_PAT_RAW',
    'Datum narození',
    'Datum narození pacienta uložené ve zdrojovém systému.',
    'DATE',
    'http://loinc.org/21112-8',
    2,
    NULL,
    'Date',
    'birth_date DATE',
    NULL,
    NULL,
    NULL
),
(
    'COL_PAT_RAW_SEX_CODE',
    'TBL_PAT_RAW',
    'Kód pohlaví',
    'Kód pohlaví dle nemocničního číselníku.',
    'VARCHAR',
    'http://snomed.info/sct/263495000',
    3,
    NULL,
    'character',
    'sex_code VARCHAR(10)',
    NULL,
    NULL,
    NULL
),
(
    'COL_PAT_RAW_CREATED_AT',
    'TBL_PAT_RAW',
    'Čas vytvoření záznamu',
    'Časová značka vytvoření záznamu ve zdrojovém systému.',
    'TIMESTAMP',
    NULL,
    4,
    NULL,
    'POSIXct',
    'created_at TIMESTAMP WITH TIME ZONE NOT NULL',
    NULL,
    NULL,
    NULL
),
(
    'COL_PAT_CLN_PATIENT_KEY',
    'TBL_PAT_CLN',
    'Pacientský klíč',
    'Stabilní interní klíč používaný v čisté vrstvě datového skladu.',
    'BIGINT',
    NULL,
    1,
    'PK',
    'integer',
    'patient_key BIGINT NOT NULL PRIMARY KEY',
    NULL,
    NULL,
    'PRIMARY KEY (patient_key)'
),
(
    'COL_PAT_CLN_ANON_ID',
    'TBL_PAT_CLN',
    'Pseudonymizovaný identifikátor',
    'Pseudonymizovaný identifikátor pacienta použitelný mimo zdrojový systém.',
    'VARCHAR',
    NULL,
    2,
    'UK',
    'character',
    'anon_id VARCHAR(64) NOT NULL UNIQUE',
    NULL,
    NULL,
    NULL
),
(
    'COL_PAT_CLN_AGE_GROUP',
    'TBL_PAT_CLN',
    'Věková skupina',
    'Odvozená věková skupina pacienta používaná v analytických pohledech.',
    'VARCHAR',
    NULL,
    3,
    NULL,
    'character',
    'age_group VARCHAR(20)',
    'CASE WHEN age < 18 THEN ''0-17'' ELSE ''18+'' END',
    NULL,
    NULL
),
(
    'COL_PAT_CLN_ACTIVE_FLAG',
    'TBL_PAT_CLN',
    'Aktivní záznam',
    'Příznak označující aktivní pacientský záznam.',
    'BOOLEAN',
    NULL,
    4,
    NULL,
    'integer',
    'is_active BOOLEAN NOT NULL DEFAULT TRUE',
    NULL,
    NULL,
    NULL
),
(
    'COL_LAB_RAW_RESULT_ID',
    'TBL_LAB_RAW',
    'ID výsledku',
    'Jedinečný identifikátor laboratorního výsledku.',
    'BIGINT',
    NULL,
    1,
    'PK',
    'integer',
    'result_id BIGINT NOT NULL PRIMARY KEY',
    NULL,
    NULL,
    'PRIMARY KEY (result_id)'
),
(
    'COL_LAB_RAW_PATIENT_ID',
    'TBL_LAB_RAW',
    'ID pacienta',
    'Odkaz na pacienta, ke kterému výsledek náleží.',
    'BIGINT',
    'http://snomed.info/sct/116154003',
    2,
    'FK',
    'integer',
    'patient_id BIGINT NOT NULL',
    'DS_PATIENTS.patient_id',
    NULL,
    NULL
),
(
    'COL_LAB_RAW_LOINC_CODE',
    'TBL_LAB_RAW',
    'LOINC kód testu',
    'Identifikátor laboratorního testu podle LOINC.',
    'VARCHAR',
    'http://loinc.org/LP29684-5',
    3,
    NULL,
    'character',
    'loinc_code VARCHAR(20) NOT NULL',
    NULL,
    NULL,
    NULL
),
(
    'COL_LAB_RAW_RESULT_VALUE',
    'TBL_LAB_RAW',
    'Naměřená hodnota',
    'Číselná naměřená hodnota laboratorního vyšetření.',
    'DECIMAL',
    NULL,
    4,
    NULL,
    'numeric',
    'result_value DECIMAL(12,4)',
    NULL,
    NULL,
    NULL
),
(
    'COL_CAP_ANA_REPORT_MONTH',
    'TBL_CAP_ANA',
    'Měsíc reportu',
    'Kalendářní měsíc, za který jsou agregované provozní ukazatele počítány.',
    'DATE',
    NULL,
    1,
    'PK',
    'Date',
    'report_month DATE NOT NULL',
    NULL,
    NULL,
    'PRIMARY KEY (report_month, department_code)'
),
(
    'COL_CAP_ANA_DEPARTMENT_CODE',
    'TBL_CAP_ANA',
    'Kód oddělení',
    'Kód kliniky nebo oddělení, ke kterému se agregace vztahuje.',
    'VARCHAR',
    NULL,
    2,
    'PK',
    'character',
    'department_code VARCHAR(20) NOT NULL',
    NULL,
    NULL,
    NULL
),
(
    'COL_CAP_ANA_ADMISSIONS',
    'TBL_CAP_ANA',
    'Počet příjmů',
    'Celkový počet hospitalizačních příjmů v daném měsíci a oddělení.',
    'INTEGER',
    NULL,
    3,
    NULL,
    'integer',
    'admissions_count INTEGER NOT NULL',
    NULL,
    NULL,
    NULL
),
(
    'COL_CAP_ANA_AVG_LOS',
    'TBL_CAP_ANA',
    'Průměrná délka hospitalizace',
    'Průměrná délka hospitalizace ve dnech.',
    'DECIMAL',
    NULL,
    4,
    NULL,
    'numeric',
    'avg_length_of_stay DECIMAL(6,2)',
    NULL,
    NULL,
    NULL
);
