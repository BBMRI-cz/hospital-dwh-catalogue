-- ============================================================
-- Mock warehouse data — Local Metadata HealthDCAT-AP  (lm_* tables)
-- ============================================================
-- Runs once on first Postgres container start via initdb.d/.
-- Covers every meaningful field-value combination so that the
-- application can exercise all code paths with realistic data.
--
-- Combination matrix:
--   ContactPoint : email+page | email only | page only | neither
--   Agent        : with / without contact_point
--   Dataset      : all optional fields | partial | minimal
--                  access_rights : http://publications.europa.eu/resource/authority/access-right/{PUBLIC,RESTRICTED,NON_PUBLIC}
--                  applicable_legislation : GDPR / GDPR;EHDS / EHDS / GDPR;EHDS;NIS2
--                  health_category : patient_data / diagnostic_data / medication_data / administrative_data / research_data
--   Distribution : db_layer = raw | clean | analytical | NULL
--                  format   : PARQUET | DELTA | CSV | JSON | ORC | NULL
--                  rights   : internal | restricted | public | NULL
--   Attribute    : key_db   : PK | FK | UK | NULL
--                  datatype : VARCHAR | INTEGER | BIGINT | DATE | TIMESTAMP | BOOLEAN | DECIMAL | NULL
--                  type_r   : character | integer | numeric | Date | POSIXct | NULL
--                  definition chain : all pom fields | pom1 only | none
--                  property_url : SNOMED URI | LOINC URI | NULL
-- ============================================================

-- ── ContactPoints ────────────────────────────────────────────
-- Insert with explicit IDs so subsequent FKs can use literals.
INSERT INTO metadata."lm_contact_point" (id, email, contact_page)
OVERRIDING SYSTEM VALUE VALUES
-- 1: both email AND page
(1, 'data@hospital.cz',     'https://hospital.cz/data/contact'),
-- 2: email only
(2, 'labs@hospital.cz',     NULL),
-- 3: page only
(3, NULL,                   'https://hospital.cz/radiology/contact'),
-- 4: neither  (ContactPoint record exists but carries no contact info)
(4, NULL,                   NULL);

SELECT setval(pg_get_serial_sequence('metadata."lm_contact_point"', 'id'), 4);

-- ── Agents ───────────────────────────────────────────────────
INSERT INTO metadata."lm_agent" (name, contact_point_id) VALUES
-- with contact (email+page)
('AGENT_DWH',        1),
-- with contact (email only)
('AGENT_LABS',       2),
-- with contact (page only)  — used as HDAB in several datasets
('AGENT_HDAB',       3),
-- no contact at all
('AGENT_NO_CONTACT', NULL);

-- ── Catalog ──────────────────────────────────────────────────
INSERT INTO metadata."lm_catalog" (name, title, description, publisher_id, applicable_legislation) VALUES
(
    'CAT_LM',
    'Katalog lokálních metadat',
    'Katalog HealthDCAT-AP pro Datový sklad nemocnice. Zahrnuje klinická, laboratorní, zobrazovací a administrativní data.',
    'AGENT_DWH',
    'GDPR;EHDS'
);

-- ── Datasets ─────────────────────────────────────────────────
-- DS_PATIENTS: ALL optional fields filled
INSERT INTO metadata."lm_dataset" (
    name, title, version, description, theme, publisher_id, license, conformed_to,
    issued, modified, keyword, source, creator, contact_point_id, rights_holder,
    provenance, catalog_id,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PATIENTS',
    'Demografická data pacientů',
    '3.1.0',
    'Základní demografické údaje pacientů: jméno, rodné číslo, pohlaví, datum narození, adresa, kontaktní informace a pojistné údaje.',
    'http://purl.bioontology.org/ontology/MESH/D000293',
    'AGENT_DWH',
    'https://creativecommons.org/licenses/by/4.0/',
    'https://healthdcat-ap.eu/spec/v6',
    '2020-01-15 00:00:00+01',
    '2025-06-01 00:00:00+02',
    'pacient,demografie,jméno,rodné číslo,pohlaví',
    'https://nemis.hospital.cz/api/patients',
    'Klinický tým; IT oddělení',
    1,
    'Nemocnice a.s.',
    'Data pocházejí z nemocničního informačního systému NEMIS. ETL pipeline spouštěn denně.',
    'CAT_LM',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_LABS: partial optionals (title + description + keyword + contact_point only)
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_LABS',
    'Laboratorní výsledky',
    'Výsledky laboratorních vyšetření: krevní obraz, biochemie, mikrobiologie, koagulace.',
    'laboratoř,výsledky,krevní obraz,biochemie,mikrobiologie',
    2,
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_RADIOLOGY: description only; different access_rights + legislation
INSERT INTO metadata."lm_dataset" (
    name, title, description,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_RADIOLOGY',
    'Radiologické zobrazování',
    'DICOM metadata, zprávy a závěry z CT, MRI, RTG a ultrazvuku.',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_PHARMACY: source + keyword; PUBLIC access; EHDS only legislation
INSERT INTO metadata."lm_dataset" (
    name, title, keyword, source, publisher_id,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PHARMACY',
    'Farmakoterapie a lékárna',
    'léky,předpisy,ATC kódy,dávkování,aplikace',
    'https://lekarna.hospital.cz/api',
    'AGENT_LABS',
    'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
    'EHDS',
    'medication_data',
    'AGENT_HDAB'
);

-- DS_ONCOLOGY: NO optional fields whatsoever; minimal dataset
INSERT INTO metadata."lm_dataset" (
    name,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_ONCOLOGY',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS;NIS2',
    'research_data',
    'AGENT_HDAB'
);

-- DS_ADMIN: administrative_data health_category; all mandatory + creator + rights_holder
INSERT INTO metadata."lm_dataset" (
    name, title, creator, rights_holder,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_ADMIN',
    'Administrativní a fakturační data',
    'Ekonomické oddělení; IT oddělení',
    'Nemocnice a.s. — Ekonomický úsek',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'administrative_data',
    'AGENT_NO_CONTACT'
);

-- ── Distributions ────────────────────────────────────────────
-- db_layer  : raw | clean | analytical | NULL
-- format    : PARQUET | DELTA | CSV | JSON | ORC | NULL
-- rights    : internal | restricted | public | NULL
-- byte_size : present on some rows, NULL on others

-- DS_PATIENTS – raw: all optional filled; format PARQUET; rights internal
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, description, format, conformed_to, byte_size,
    rights, issued, modified, access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PATIENTS_RAW',
    'DS_PATIENTS',
    'Surová data pacientů (Raw)',
    'Surovená data přímo z EMR systému bez čištění.',
    'PARQUET',
    'https://healthdcat-ap.eu/spec/v6',
    524288000,
    'internal',
    '2020-01-15 00:00:00+01',
    '2025-06-01 00:00:00+02',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_PATIENTS – clean: partial optional; format DELTA; rights restricted
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size,
    rights, access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PATIENTS_CLEAN',
    'DS_PATIENTS',
    'Čistá data pacientů (Clean)',
    'DELTA',
    209715200,
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_clean',
    'GDPR;EHDS',
    'clean'
);

-- DS_PATIENTS – analytical: minimal optional; format ORC; rights public; byte_size NULL
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PATIENTS_ANALYTICAL',
    'DS_PATIENTS',
    'Analytická vrstva pacientů',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_patient',
    'GDPR;EHDS',
    'analytical'
);

-- DS_LABS – raw: format CSV; rights internal; conformed_to filled
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, conformed_to, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_LABS_RAW',
    'DS_LABS',
    'Surová laboratorní data',
    'CSV',
    'https://loinc.org/spec',
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_LABS – clean: format JSON; no rights; with issued/modified
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, issued, modified,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_LABS_CLEAN',
    'DS_LABS',
    'Čistá laboratorní data',
    'JSON',
    '2021-03-01 00:00:00+01',
    '2025-05-15 00:00:00+02',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_clean',
    'GDPR;EHDS',
    'clean'
);

-- DS_RADIOLOGY – raw: all optional NULL except title; no db_layer (NULL)
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_RADIOLOGY_NULL_LAYER',
    'DS_RADIOLOGY',
    'Radiologická distribuce (vrstva neurčena)',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.radiology_raw',
    'GDPR',
    NULL
);

-- DS_PHARMACY – analytical; format PARQUET; rights public
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, description, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PHARMACY_ANALYTICAL',
    'DS_PHARMACY',
    'Analytická farmaceutická data',
    'Dimenzionální tabulka léků pro analytické dotazy.',
    'PARQUET',
    'public',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_medication',
    'EHDS',
    'analytical'
);

-- DS_ONCOLOGY – clean; minimal optionals
INSERT INTO metadata."lm_distribution" (
    name, dataset_name,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_ONCOLOGY_CLEAN',
    'DS_ONCOLOGY',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.oncology_clean',
    'GDPR;EHDS;NIS2',
    'clean'
);

-- DS_ADMIN – raw; NULL db_layer; all optional fields
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, description, format, byte_size,
    issued, access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_ADMIN_RAW',
    'DS_ADMIN',
    'Surová administrativní data',
    'Fakturace, pojistné nároky a platby z fakturačního systému.',
    'CSV',
    104857600,
    '2019-09-01 00:00:00+02',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.billing_raw',
    'GDPR',
    'raw'
);

-- ── Attributes ───────────────────────────────────────────────
-- Covers every combination of: key_db × datatype × type_r
-- definition chain, property_url, and var_order.

-- ── DIST_PATIENTS_RAW ────────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title, description,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
-- PK / BIGINT / integer — full definition chain + SNOMED URI
(
    'ATTR_PAT_RAW_PATIENT_ID',  'DIST_PATIENTS_RAW', 'ID pacienta',
    'Surrogate klíč pacienta generovaný sekvencí DWH.',
    'BIGINT',
    'http://snomed.info/sct/406547006',  -- SNOMED: Patient identifier
    1, 'PK', 'integer',
    'patient_id BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY',
    'seq_patients.NEXTVAL',
    'CAST(seq_patients.NEXTVAL AS BIGINT)',
    'BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY'
),
-- PK / VARCHAR / character — no property_url; no definition chain
(
    'ATTR_PAT_RAW_RODNE_CISLO',  'DIST_PATIENTS_RAW', 'Rodné číslo',
    'Rodné číslo pacienta (pseudonymizováno SHA-256).',
    'VARCHAR', NULL,
    2, 'UK', 'character',
    'rodne_cislo VARCHAR(64) NOT NULL',
    NULL, NULL, NULL
),
-- NULL key / VARCHAR / character — definition_pk_pom1 only
(
    'ATTR_PAT_RAW_FIRST_NAME',   'DIST_PATIENTS_RAW', 'Křestní jméno',
    'Křestní jméno pacienta.',
    'VARCHAR', NULL,
    3, NULL, 'character',
    'first_name VARCHAR(100)',
    'UPPER(first_name)',
    NULL, NULL
),
-- NULL key / VARCHAR / character
(
    'ATTR_PAT_RAW_LAST_NAME',    'DIST_PATIENTS_RAW', 'Příjmení',
    'Příjmení pacienta.',
    'VARCHAR', NULL,
    4, NULL, 'character',
    'last_name VARCHAR(100)',
    NULL, NULL, NULL
),
-- NULL key / DATE / Date — LOINC URI for birth date
(
    'ATTR_PAT_RAW_DOB',          'DIST_PATIENTS_RAW', 'Datum narození',
    'Datum narození pacienta.',
    'DATE',
    'http://loinc.org/21112-8',  -- LOINC: Birth date
    5, NULL, 'Date',
    'date_of_birth DATE',
    NULL, NULL, NULL
),
-- FK / INTEGER / integer — SNOMED for gender concept; full definition chain
(
    'ATTR_PAT_RAW_GENDER_ID',    'DIST_PATIENTS_RAW', 'Pohlaví (FK)',
    'Odkaz na číselník pohlaví.',
    'INTEGER',
    'http://snomed.info/sct/263495000',  -- SNOMED: Gender
    6, 'FK', 'integer',
    'gender_id INTEGER REFERENCES dim_gender(gender_id)',
    'dim_gender.gender_id',
    'CAST(dim_gender.gender_id AS INTEGER)',
    'INTEGER REFERENCES dim_gender(gender_id)'
),
-- NULL key / TIMESTAMP / POSIXct — timestamp of record creation
(
    'ATTR_PAT_RAW_CREATED_AT',   'DIST_PATIENTS_RAW', 'Vytvořeno',
    'Časová značka vytvoření záznamu.',
    'TIMESTAMP', NULL,
    7, NULL, 'POSIXct',
    'created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
    NULL, NULL, NULL
),
-- NULL key / BOOLEAN / integer (R uses integer for logical) — active flag
(
    'ATTR_PAT_RAW_IS_ACTIVE',    'DIST_PATIENTS_RAW', 'Aktivní',
    'Příznak aktivního pacienta (1 = aktivní, 0 = archivován).',
    'BOOLEAN', NULL,
    8, NULL, 'integer',
    'is_active BOOLEAN NOT NULL DEFAULT TRUE',
    NULL, NULL, NULL
),
-- NULL key / DECIMAL / numeric — body weight in kg
(
    'ATTR_PAT_RAW_WEIGHT_KG',    'DIST_PATIENTS_RAW', 'Hmotnost (kg)',
    'Tělesná hmotnost pacienta v kilogramech.',
    'DECIMAL',
    'http://loinc.org/3141-9',  -- LOINC: Body weight
    9, NULL, 'numeric',
    'weight_kg DECIMAL(5,2)',
    NULL, NULL, NULL
),
-- NULL key / NULL datatype / NULL type_r — free-text note column (no typing metadata)
(
    'ATTR_PAT_RAW_NOTE',         'DIST_PATIENTS_RAW', 'Poznámka',
    'Volný textový komentář ke kartě pacienta.',
    NULL, NULL,
    10, NULL, NULL,
    NULL, NULL, NULL, NULL
);

-- ── DIST_PATIENTS_CLEAN ──────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title, description,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
-- PK / BIGINT / integer — no definition chain
(
    'ATTR_PAT_CLN_PATIENT_ID',   'DIST_PATIENTS_CLEAN', 'ID pacienta',
    'Surrogate klíč pacienta (čistá vrstva).',
    'BIGINT', NULL,
    1, 'PK', 'integer',
    'patient_id BIGINT NOT NULL PRIMARY KEY',
    NULL, NULL, NULL
),
-- NULL key / INTEGER / numeric — age derived column; pom1 only
(
    'ATTR_PAT_CLN_AGE',          'DIST_PATIENTS_CLEAN', 'Věk (roky)',
    'Věk pacienta k datu extrakce (odvozeno z data narození).',
    'INTEGER', NULL,
    2, NULL, 'numeric',
    'age_years INTEGER',
    'DATE_PART(''year'', AGE(date_of_birth))',
    NULL, NULL
),
-- NULL key / DECIMAL / numeric — BMI; full definition chain
(
    'ATTR_PAT_CLN_BMI',          'DIST_PATIENTS_CLEAN', 'BMI',
    'Index tělesné hmotnosti (kg/m²).',
    'DECIMAL',
    'http://loinc.org/39156-5',  -- LOINC: BMI
    3, NULL, 'numeric',
    'bmi DECIMAL(4,1)',
    'weight_kg / (height_m * height_m)',
    'ROUND(weight_kg / NULLIF(height_m * height_m, 0), 1)',
    'DECIMAL(4,1) GENERATED ALWAYS AS (ROUND(weight_kg / NULLIF(height_m * height_m, 0), 1)) STORED'
),
-- FK / VARCHAR / character — LOINC URI; no definition
(
    'ATTR_PAT_CLN_GENDER_CODE',  'DIST_PATIENTS_CLEAN', 'Kód pohlaví',
    'Kód pohlaví dle číselníku DASTA.',
    'VARCHAR',
    'http://snomed.info/sct/263495000',
    4, 'FK', 'character',
    NULL, NULL, NULL, NULL
),
-- UK / VARCHAR / character — anonymised identifier
(
    'ATTR_PAT_CLN_ANON_ID',      'DIST_PATIENTS_CLEAN', 'Anonymizovaný ID',
    'Pseudonymizovaný identifikátor (SHA-256 z rodného čísla).',
    'VARCHAR', NULL,
    5, 'UK', 'character',
    'anon_id VARCHAR(64) NOT NULL UNIQUE',
    NULL, NULL, NULL
);

-- ── DIST_PATIENTS_ANALYTICAL ─────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title, description,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
-- PK / BIGINT / integer — surrogate dim key
(
    'ATTR_PAT_ANA_DIM_KEY',      'DIST_PATIENTS_ANALYTICAL', 'Dimenzní klíč',
    'Surrogate klíč dimenze pacientů (star schema).',
    'BIGINT', NULL,
    1, 'PK', 'integer',
    'dim_patient_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY',
    NULL, NULL, NULL
),
-- FK / BIGINT / integer — natural key back-reference
(
    'ATTR_PAT_ANA_SRC_KEY',      'DIST_PATIENTS_ANALYTICAL', 'Zdrojový klíč',
    'Odkaz na patient_id ve zdrojovém systému.',
    'BIGINT', NULL,
    2, 'FK', 'integer',
    'src_patient_id BIGINT NOT NULL',
    NULL, NULL, NULL
),
-- NULL key / DATE / Date — SCD2 effective date
(
    'ATTR_PAT_ANA_VALID_FROM',   'DIST_PATIENTS_ANALYTICAL', 'Platnost od',
    'Datum začátku platnosti záznamu (SCD typ 2).',
    'DATE', NULL,
    3, NULL, 'Date',
    'valid_from DATE NOT NULL',
    NULL, NULL, NULL
),
-- NULL key / NULL datatype / NULL type_r — all-null combo (no typing)
(
    'ATTR_PAT_ANA_SEGMENT',      'DIST_PATIENTS_ANALYTICAL', 'Segment',
    'Marketingový segment pacienta (volný text, bez schématu).',
    NULL, NULL,
    4, NULL, NULL,
    NULL, NULL, NULL, NULL
);

-- ── DIST_LABS_RAW ────────────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
-- PK / BIGINT + LOINC for order concept
(
    'ATTR_LAB_RAW_ORDER_ID',     'DIST_LABS_RAW', 'ID objednávky',
    'BIGINT', 'http://loinc.org/26436-6', 1, 'PK', 'integer',
    'order_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL
),
-- FK / INTEGER — patient reference; SNOMED patient
(
    'ATTR_LAB_RAW_PATIENT_ID',   'DIST_LABS_RAW', 'ID pacienta',
    'INTEGER', 'http://snomed.info/sct/406547006', 2, 'FK', 'integer',
    'patient_id INTEGER NOT NULL', NULL, NULL, NULL
),
-- NULL / VARCHAR / character — LOINC test code
(
    'ATTR_LAB_RAW_TEST_CODE',    'DIST_LABS_RAW', 'Kód testu (LOINC)',
    'VARCHAR', 'http://loinc.org/24357-6', 3, NULL, 'character',
    'test_code VARCHAR(20) NOT NULL', NULL, NULL, NULL
),
-- NULL / DECIMAL / numeric — numeric test value
(
    'ATTR_LAB_RAW_VALUE_NUM',    'DIST_LABS_RAW', 'Číselná hodnota',
    'DECIMAL', NULL, 4, NULL, 'numeric',
    'value_num DECIMAL(12,4)', NULL, NULL, NULL
),
-- NULL / TIMESTAMP / POSIXct — result timestamp
(
    'ATTR_LAB_RAW_RESULT_TS',    'DIST_LABS_RAW', 'Čas výsledku',
    'TIMESTAMP', NULL, 5, NULL, 'POSIXct',
    'result_ts TIMESTAMP WITH TIME ZONE', NULL, NULL, NULL
);

-- ── DIST_LABS_CLEAN ──────────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
(
    'ATTR_LAB_CLN_RESULT_ID',    'DIST_LABS_CLEAN', 'ID výsledku',
    'BIGINT', NULL, 1, 'PK', 'integer',
    'result_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL
),
-- NULL / BOOLEAN / integer — critical flag
(
    'ATTR_LAB_CLN_IS_CRITICAL',  'DIST_LABS_CLEAN', 'Kritická hodnota',
    'BOOLEAN', NULL, 2, NULL, 'integer',
    'is_critical BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL
),
-- NULL / NULL / NULL
(
    'ATTR_LAB_CLN_COMMENT',      'DIST_LABS_CLEAN', 'Komentář',
    NULL, NULL, 3, NULL, NULL,
    NULL, NULL, NULL, NULL
);

-- ── DIST_RADIOLOGY_NULL_LAYER ────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
(
    'ATTR_RAD_STUDY_UID',        'DIST_RADIOLOGY_NULL_LAYER', 'StudyInstanceUID',
    'VARCHAR', NULL, 1, 'UK', 'character',
    'study_instance_uid VARCHAR(128) UNIQUE NOT NULL', NULL, NULL, NULL
),
-- NULL / INTEGER / integer — number of series
(
    'ATTR_RAD_SERIES_COUNT',     'DIST_RADIOLOGY_NULL_LAYER', 'Počet sérií',
    'INTEGER', NULL, 2, NULL, 'integer',
    'series_count INTEGER', NULL, NULL, NULL
),
-- NULL / NULL / NULL — free text impression
(
    'ATTR_RAD_IMPRESSION',       'DIST_RADIOLOGY_NULL_LAYER', 'Závěr',
    NULL, NULL, 3, NULL, NULL,
    NULL, NULL, NULL, NULL
);

-- ── DIST_PHARMACY_ANALYTICAL ─────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
(
    'ATTR_PHR_DIM_MED_KEY',      'DIST_PHARMACY_ANALYTICAL', 'Dimenzní klíč léku',
    'BIGINT', NULL, 1, 'PK', 'integer',
    'dim_medication_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY',
    NULL, NULL, NULL
),
(
    'ATTR_PHR_ATC_CODE',         'DIST_PHARMACY_ANALYTICAL', 'ATC Kód',
    'VARCHAR',
    'http://www.whocc.no/atc',   -- WHO ATC ontology URI
    2, 'UK', 'character',
    'atc_code VARCHAR(10) UNIQUE NOT NULL', NULL, NULL, NULL
),
-- NULL / DECIMAL / numeric — defined daily dose
(
    'ATTR_PHR_DDD',              'DIST_PHARMACY_ANALYTICAL', 'DDD (mg)',
    'DECIMAL',
    'http://www.whocc.no/ddd',
    3, NULL, 'numeric',
    'ddd_mg DECIMAL(8,3)', NULL, NULL, NULL
);

-- ── DIST_ONCOLOGY_CLEAN ──────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
(
    'ATTR_ONC_DIAGNOSIS_ID',     'DIST_ONCOLOGY_CLEAN', 'ID diagnózy',
    'BIGINT', NULL, 1, 'PK', 'integer',
    'diagnosis_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL
),
-- NULL / VARCHAR / character — ICD-O morphology code; SNOMED
(
    'ATTR_ONC_MORPHOLOGY',       'DIST_ONCOLOGY_CLEAN', 'Morfologie (ICD-O)',
    'VARCHAR',
    'http://snomed.info/sct/400177003',  -- SNOMED: Morphology
    2, NULL, 'character',
    'morphology_code VARCHAR(10)',
    NULL, NULL, NULL
),
-- NULL / DATE / Date — diagnosis date
(
    'ATTR_ONC_DX_DATE',          'DIST_ONCOLOGY_CLEAN', 'Datum diagnózy',
    'DATE', NULL, 3, NULL, 'Date',
    'diagnosis_date DATE',
    NULL, NULL, NULL
);

-- ── DIST_ADMIN_RAW ────────────────────────────────────────────
INSERT INTO metadata."lm_attribute" (
    name, distribution_name, title,
    datatype, property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
(
    'ATTR_ADM_ENCOUNTER_ID',     'DIST_ADMIN_RAW', 'ID návštěvy',
    'BIGINT', NULL, 1, 'PK', 'integer',
    'encounter_id BIGINT NOT NULL PRIMARY KEY',
    'seq_encounter.NEXTVAL',
    'CAST(seq_encounter.NEXTVAL AS BIGINT)',
    'BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY'
),
(
    'ATTR_ADM_PATIENT_ID',       'DIST_ADMIN_RAW', 'ID pacienta',
    'BIGINT', 'http://snomed.info/sct/406547006', 2, 'FK', 'integer',
    'patient_id BIGINT NOT NULL', NULL, NULL, NULL
),
(
    'ATTR_ADM_TOTAL_CHARGE',     'DIST_ADMIN_RAW', 'Celková částka',
    'DECIMAL', NULL, 3, NULL, 'numeric',
    'total_charge DECIMAL(12,2)', NULL, NULL, NULL
),
(
    'ATTR_ADM_DISCHARGE_TS',     'DIST_ADMIN_RAW', 'Datum propuštění',
    'TIMESTAMP', NULL, 4, NULL, 'POSIXct',
    'discharge_ts TIMESTAMP WITH TIME ZONE', NULL, NULL, NULL
),
-- NULL/NULL/NULL row for admin notes
(
    'ATTR_ADM_NOTE',             'DIST_ADMIN_RAW', 'Poznámka k faktuře',
    NULL, NULL, 5, NULL, NULL,
    NULL, NULL, NULL, NULL
);