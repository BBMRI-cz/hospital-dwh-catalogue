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
INSERT INTO metadata."lm_agent" (name, contact_point_id, description) VALUES
-- with contact (email+page)
('AGENT_DWH',        1, 'DWH team responsible for local metadata management and ETL pipelines.'),
-- with contact (email only)
('AGENT_LABS',       2, 'Laboratory information system team managing diagnostic data.'),
-- with contact (page only)  — used as HDAB in several datasets
('AGENT_HDAB',       3, 'Health Data Access Body overseeing access to hospital datasets.'),
-- no contact at all
('AGENT_NO_CONTACT', NULL, NULL);

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
    name, title, version, description, theme, publisher_id, conforms_to,
    issued, modified, keyword, source, creator, contact_point_id,
    provenance, catalog_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id, custodian_id
) VALUES (
    'DS_PATIENTS',
    'Demografická data pacientů',
    '3.1.0',
    'Základní demografické údaje pacientů: jméno, rodné číslo, pohlaví, datum narození, adresa, kontaktní informace a pojistné údaje.',
    'http://purl.bioontology.org/ontology/MESH/D000293',
    'AGENT_DWH',
    'https://healthdcat-ap.eu/spec/v6',
    '2020-01-15 00:00:00+01',
    '2025-06-01 00:00:00+02',
    'pacient,demografie,jméno,rodné číslo,pohlaví',
    NULL,
    'AGENT_DWH',
    1,
    'Data pocházejí z nemocničního informačního systému NEMIS. ETL pipeline spouštěn denně.',
    'CAT_LM',
    'https://nemis.hospital.cz/dataset/DS_PATIENTS',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB',
    'AGENT_DWH'
);

-- DS_LABS: partial optionals (title + description + keyword + contact_point only)
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_LABS',
    'Laboratorní výsledky',
    'Výsledky laboratorních vyšetření: krevní obraz, biochemie, mikrobiologie, koagulace.',
    'laboratoř,výsledky,krevní obraz,biochemie,mikrobiologie',
    2,
    'https://nemis.hospital.cz/dataset/DS_LABS',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_RADIOLOGY: description only; different access_rights + legislation
INSERT INTO metadata."lm_dataset" (
    name, title, description, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_RADIOLOGY',
    'Radiologické zobrazování',
    'DICOM metadata, zprávy a závěry z CT, MRI, RTG a ultrazvuku.',
    3,
    'https://nemis.hospital.cz/dataset/DS_RADIOLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_PHARMACY: source + keyword; PUBLIC access; EHDS only legislation
INSERT INTO metadata."lm_dataset" (
    name, title, keyword, source, publisher_id, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PHARMACY',
    'Farmakoterapie a lékárna',
    'léky,předpisy,ATC kódy,dávkování,aplikace',
    'DS_PATIENTS',
    'AGENT_LABS',
    1,
    'https://nemis.hospital.cz/dataset/DS_PHARMACY',
    'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
    'http://publications.europa.eu/resource/authority/access-right/PUBLIC',
    'EHDS',
    'medication_data',
    'AGENT_HDAB'
);

-- DS_ONCOLOGY: NO optional fields whatsoever; minimal dataset
INSERT INTO metadata."lm_dataset" (
    name, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_ONCOLOGY',
    1,
    'https://nemis.hospital.cz/dataset/DS_ONCOLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS;NIS2',
    'research_data',
    'AGENT_HDAB'
);

-- DS_ADMIN: administrative_data health_category; all mandatory + creator
INSERT INTO metadata."lm_dataset" (
    name, title, creator, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_ADMIN',
    'Administrativní a fakturační data',
    'AGENT_DWH',
    1,
    'https://nemis.hospital.cz/dataset/DS_ADMIN',
    'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'administrative_data',
    'AGENT_NO_CONTACT'
);

-- DS_ICU: intensive care; NON_PUBLIC; GDPR;EHDS; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id, custodian_id
) VALUES (
    'DS_ICU',
    'Data jednotky intenzivní péče',
    'Monitorovací data z JIP: vitální funkce, ventilace, hemodynamika, léčiva.',
    'JIP,intenzivní péče,ventilace,vitální funkce,hemodynamika',
    1,
    'https://nemis.hospital.cz/dataset/DS_ICU',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB',
    'AGENT_DWH'
);

-- DS_SURGERY: surgical records; NON_PUBLIC; GDPR;EHDS; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, publisher_id, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_SURGERY',
    'Chirurgické výkony a operační záznamy',
    'Data o chirurgických výkonech: kódy výkonů, délka operace, anestézie, komplikace.',
    'chirurgie,operace,výkony,anestézie,komplikace',
    'AGENT_DWH',
    1,
    'https://nemis.hospital.cz/dataset/DS_SURGERY',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_CARDIOLOGY: ECG + cardiology; RESTRICTED; GDPR; diagnostic_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_CARDIOLOGY',
    'Kardiologická data a EKG',
    'EKG záznamy, echokardiografie, Holter monitorování a katetrizační nálezy.',
    'kardiologie,EKG,echo,Holter,katetrizace',
    3,
    'https://nemis.hospital.cz/dataset/DS_CARDIOLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_NEUROLOGY: neurological data; RESTRICTED; GDPR;EHDS; diagnostic_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_NEUROLOGY',
    'Neurologická klinická data',
    'EEG, EMG, CT mozkové skeny, MRI mozku, neurologické nálezy a diagnózy.',
    'neurologie,EEG,EMG,mozkový sken,MRI',
    1,
    'https://nemis.hospital.cz/dataset/DS_NEUROLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_PATHOLOGY: pathology results; NON_PUBLIC; GDPR;EHDS; diagnostic_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, publisher_id, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PATHOLOGY',
    'Patologicko-anatomické nálezy',
    'Histologické, cytologické a molekulárně-patologické nálezy z biopsií a pitvání.',
    'patologie,histologie,cytologie,biopsie,pitva',
    'AGENT_LABS',
    1,
    'https://nemis.hospital.cz/dataset/DS_PATHOLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_MICROBIOLOGY: cultures + antibiograms; RESTRICTED; GDPR;EHDS; diagnostic_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_MICROBIOLOGY',
    'Mikrobiologické kultivace a antibiogramy',
    'Výsledky kultivací, citlivosti na antibiotika, PCR průkazy patogenů.',
    'mikrobiologie,kultivace,antibiogram,PCR,patogeny',
    2,
    'https://nemis.hospital.cz/dataset/DS_MICROBIOLOGY',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- DS_EMERGENCY: emergency department; RESTRICTED; GDPR;EHDS; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_EMERGENCY',
    'Data urgentního příjmu',
    'Triáž, diagnózy, doby ošetření a výsledky léčby na urgentním příjmu.',
    'urgence,příjem,triáž,diagnóza,ošetření',
    2,
    'https://nemis.hospital.cz/dataset/DS_EMERGENCY',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_PSYCHIATRY: mental health; NON_PUBLIC; GDPR;EHDS;NIS2; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PSYCHIATRY',
    'Psychiatrická a psychologická data',
    'Psychiatrické diagnózy, psychologická vyšetření, medikace a průběhy hospitalizací.',
    'psychiatrie,psychologie,diagnózy,medikace,hospitalizace',
    1,
    'https://nemis.hospital.cz/dataset/DS_PSYCHIATRY',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS;NIS2',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_PEDIATRICS: pediatric patient data; NON_PUBLIC; GDPR;EHDS; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, publisher_id, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_PEDIATRICS',
    'Pediatrická data pacientů',
    'Dětská demografie, růstové parametry, očkování, diagnózy a hospitalizace.',
    'pediatrie,děti,očkování,růst,diagnózy',
    'AGENT_DWH',
    1,
    'https://nemis.hospital.cz/dataset/DS_PEDIATRICS',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_VITAL_SIGNS: continuous monitoring; RESTRICTED; GDPR;EHDS; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id, custodian_id
) VALUES (
    'DS_VITAL_SIGNS',
    'Kontinuální monitorování vitálních funkcí',
    'Pulz, SpO2, krevní tlak, teplota, dechová frekvence — měření každých 5 minut.',
    'vitální funkce,pulz,SpO2,tlak,teplota,monitoring',
    1,
    'https://nemis.hospital.cz/dataset/DS_VITAL_SIGNS',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'patient_data',
    'AGENT_HDAB',
    'AGENT_DWH'
);

-- DS_GENOMICS: clinical genomics; NON_PUBLIC; GDPR;EHDS;NIS2; research_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_GENOMICS',
    'Klinická genomická data',
    'WGS, WES a panelové sekvenování pro diagnostiku dědičných chorob a onkogenomiku.',
    'genomika,WGS,WES,sekvenování,dědičné choroby,onkogenomika',
    1,
    'https://nemis.hospital.cz/dataset/DS_GENOMICS',
    'http://publications.europa.eu/resource/authority/dataset-type/SENSITIVE',
    'http://publications.europa.eu/resource/authority/access-right/NON_PUBLIC',
    'GDPR;EHDS;NIS2',
    'research_data',
    'AGENT_HDAB'
);

-- DS_REHABILITATION: rehabilitation & physio; RESTRICTED; GDPR; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_REHABILITATION',
    'Rehabilitace a fyzioterapie',
    'Funkční hodnocení, rehabilitační plány, fyzioterapeutické záznamy a výsledky.',
    'rehabilitace,fyzioterapie,funkční hodnocení,plány,výsledky',
    3,
    'https://nemis.hospital.cz/dataset/DS_REHABILITATION',
    'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_DIET_NUTRITION: nutrition assessments; RESTRICTED; GDPR; patient_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, publisher_id, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_DIET_NUTRITION',
    'Nutriční hnodnocení a dietetika',
    'Nutriční screening, BMI, dietetické plány, enterální a parenterální výživa.',
    'výživa,dieta,BMI,nutriční screening,parenterální výživa',
    'AGENT_LABS',
    2,
    'https://nemis.hospital.cz/dataset/DS_DIET_NUTRITION',
    'http://publications.europa.eu/resource/authority/dataset-type/ADMINISTRATIVE',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR',
    'patient_data',
    'AGENT_HDAB'
);

-- DS_IMAGING_CT: CT imaging metadata; RESTRICTED; GDPR;EHDS; diagnostic_data
INSERT INTO metadata."lm_dataset" (
    name, title, description, keyword, contact_point_id,
    identifier, type,
    access_rights, applicable_legislation, health_category, hdab_id
) VALUES (
    'DS_IMAGING_CT',
    'CT zobrazovací metadata (DICOM)',
    'DICOM metadata CT vyšetření: modalita, protokol, ozáření, závěry radiologa.',
    'CT,DICOM,zobrazování,radiologie,ozáření',
    3,
    'https://nemis.hospital.cz/dataset/DS_IMAGING_CT',
    'http://publications.europa.eu/resource/authority/dataset-type/STATISTICAL',
    'http://publications.europa.eu/resource/authority/access-right/RESTRICTED',
    'GDPR;EHDS',
    'diagnostic_data',
    'AGENT_HDAB'
);

-- ── Distributions ────────────────────────────────────────────
-- db_layer  : raw | clean | analytical | NULL
-- format    : PARQUET | DELTA | CSV | JSON | ORC | NULL
-- rights    : internal | restricted | public | NULL
-- byte_size : present on some rows, NULL on others

-- DS_PATIENTS – raw: all optional filled; format PARQUET; rights internal
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, description, format, conforms_to, byte_size,
    rights, release_date, modification_date, access_url, applicable_legislation, licence, db_layer
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
    'https://creativecommons.org/licenses/by/4.0/',
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
    name, dataset_name, title, format, conforms_to, rights,
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

-- DS_LABS – clean: format JSON; no rights; with release_date/modification_date
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, release_date, modification_date,
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
    access_url, applicable_legislation, licence, db_layer
) VALUES (
    'DIST_PHARMACY_ANALYTICAL',
    'DS_PHARMACY',
    'Analytická farmaceutická data',
    'Dimenzionální tabulka léků pro analytické dotazy.',
    'PARQUET',
    'public',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_medication',
    'EHDS',
    'https://creativecommons.org/licenses/by/4.0/',
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
    release_date, access_url, applicable_legislation, db_layer
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

-- DS_ICU – raw; PARQUET; all vitals data
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_ICU_RAW',
    'DS_ICU',
    'Surová JIP data (Raw)',
    'PARQUET',
    1073741824,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.icu_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_ICU – clean; DELTA; clean layer
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_ICU_CLEAN',
    'DS_ICU',
    'Čistá JIP data (Clean)',
    'DELTA',
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.icu_clean',
    'GDPR;EHDS',
    'clean'
);

-- DS_SURGERY – raw; CSV; all surgical records
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_SURGERY_RAW',
    'DS_SURGERY',
    'Surová chirurgická data (Raw)',
    'CSV',
    314572800,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.surgery_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_CARDIOLOGY – raw; PARQUET; ECG signals
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, conforms_to, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_CARDIOLOGY_RAW',
    'DS_CARDIOLOGY',
    'Surová kardiologická data (Raw)',
    'PARQUET',
    'https://dicom.nema.org/medical/dicom/current/output/html/part03.html',
    1073741824,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.cardiology_raw',
    'GDPR',
    'raw'
);

-- DS_CARDIOLOGY – analytical; PARQUET; aggregated
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_CARDIOLOGY_ANALYTICAL',
    'DS_CARDIOLOGY',
    'Analytická kardiologická data',
    'PARQUET',
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_cardiology',
    'GDPR',
    'analytical'
);

-- DS_NEUROLOGY – raw; JSON; EEG/EMG data
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_NEUROLOGY_RAW',
    'DS_NEUROLOGY',
    'Surová neurologická data (Raw)',
    'JSON',
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.neurology_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_PATHOLOGY – raw; CSV; biopsy results
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PATHOLOGY_RAW',
    'DS_PATHOLOGY',
    'Surová patologická data (Raw)',
    'CSV',
    52428800,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.pathology_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_MICROBIOLOGY – raw; CSV; culture results
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, conforms_to, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_MICROBIOLOGY_RAW',
    'DS_MICROBIOLOGY',
    'Surová mikrobiologická data (Raw)',
    'CSV',
    'https://www.whonet.org/',
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.microbiology_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_EMERGENCY – raw; DELTA; all ER records
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_EMERGENCY_RAW',
    'DS_EMERGENCY',
    'Surová data urgentního příjmu (Raw)',
    'DELTA',
    419430400,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.emergency_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_PSYCHIATRY – clean; PARQUET; pseudonymised
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PSYCHIATRY_CLEAN',
    'DS_PSYCHIATRY',
    'Čistá psychiatrická data (Clean)',
    'PARQUET',
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.psychiatry_clean',
    'GDPR;EHDS;NIS2',
    'clean'
);

-- DS_PEDIATRICS – raw; PARQUET; minimal optional
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_PEDIATRICS_RAW',
    'DS_PEDIATRICS',
    'Surová pediatrická data (Raw)',
    'PARQUET',
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.pediatrics_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_VITAL_SIGNS – raw; ORC; time-series data; large
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_VITAL_SIGNS_RAW',
    'DS_VITAL_SIGNS',
    'Surová data vitálních funkcí (Raw)',
    'ORC',
    2000000000,
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.vital_signs_raw',
    'GDPR;EHDS',
    'raw'
);

-- DS_GENOMICS – raw; VCF; minimal optional; large file
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_GENOMICS_RAW',
    'DS_GENOMICS',
    'Surová genomická data (Raw VCF)',
    'VCF',
    2000000000,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.genomics_raw',
    'GDPR;EHDS;NIS2',
    'raw'
);

-- DS_REHABILITATION – clean; CSV; outcome measures
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_REHABILITATION_CLEAN',
    'DS_REHABILITATION',
    'Čistá rehabilitační data (Clean)',
    'CSV',
    'restricted',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.rehabilitation_clean',
    'GDPR',
    'clean'
);

-- DS_DIET_NUTRITION – analytical; PARQUET
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_DIET_NUTRITION_ANALYTICAL',
    'DS_DIET_NUTRITION',
    'Analytická nutriční data',
    'PARQUET',
    'public',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.nutrition_analytical',
    'GDPR',
    'analytical'
);

-- DS_IMAGING_CT – raw; PARQUET; DICOM metadata only
INSERT INTO metadata."lm_distribution" (
    name, dataset_name, title, format, conforms_to, byte_size, rights,
    access_url, applicable_legislation, db_layer
) VALUES (
    'DIST_IMAGING_CT_RAW',
    'DS_IMAGING_CT',
    'Surová CT DICOM metadata (Raw)',
    'PARQUET',
    'https://dicom.nema.org/medical/dicom/current/output/html/part03.html',
    2000000000,
    'internal',
    'jdbc:postgresql://dwh-db:5432/dwh/metadata.imaging_ct_raw',
    'GDPR;EHDS',
    'raw'
);


-- ── Tables & Columns ─────────────────────────────────────────
-- One Table per Distribution; Columns carry the same physical-column
-- metadata that was previously stored in lm_attribute.
-- All Columns have mandatory title, description, and datatype.

-- ── DIST_PATIENTS_RAW ─────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PAT_RAW', 'DIST_PATIENTS_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_raw',
 'Pacienti (surová vrstva)', 'Surová data pacientů přímo z EMR systému bez čištění.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PAT_RAW_PATIENT_ID',  'TBL_PAT_RAW', 'ID pacienta',
 'Surrogate klíč pacienta generovaný sekvencí DWH.',
 'BIGINT', 'http://snomed.info/sct/406547006', 1, 'PK', 'integer',
 'patient_id BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY',
 'seq_patients.NEXTVAL', 'CAST(seq_patients.NEXTVAL AS BIGINT)',
 'BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY'),
('COL_PAT_RAW_RODNE_CISLO', 'TBL_PAT_RAW', 'Rodné číslo',
 'Rodné číslo pacienta (pseudonymizováno SHA-256).', 'VARCHAR', NULL,
 2, 'UK', 'character', 'rodne_cislo VARCHAR(64) NOT NULL', NULL, NULL, NULL),
('COL_PAT_RAW_FIRST_NAME',  'TBL_PAT_RAW', 'Křestní jméno',
 'Křestní jméno pacienta.', 'VARCHAR', NULL,
 3, NULL, 'character', 'first_name VARCHAR(100)', 'UPPER(first_name)', NULL, NULL),
('COL_PAT_RAW_LAST_NAME',   'TBL_PAT_RAW', 'Příjmení',
 'Příjmení pacienta.', 'VARCHAR', NULL,
 4, NULL, 'character', 'last_name VARCHAR(100)', NULL, NULL, NULL),
('COL_PAT_RAW_DOB',         'TBL_PAT_RAW', 'Datum narození',
 'Datum narození pacienta.', 'DATE',
 'http://loinc.org/21112-8', 5, NULL, 'Date', 'date_of_birth DATE', NULL, NULL, NULL),
('COL_PAT_RAW_GENDER_ID',   'TBL_PAT_RAW', 'Pohlaví (FK)',
 'Odkaz na číselník pohlaví.', 'INTEGER',
 'http://snomed.info/sct/263495000', 6, 'FK', 'integer',
 'gender_id INTEGER REFERENCES dim_gender(gender_id)',
 'dim_gender.gender_id', 'CAST(dim_gender.gender_id AS INTEGER)',
 'INTEGER REFERENCES dim_gender(gender_id)'),
('COL_PAT_RAW_CREATED_AT',  'TBL_PAT_RAW', 'Vytvořeno',
 'Časová značka vytvoření záznamu.', 'TIMESTAMP', NULL,
 7, NULL, 'POSIXct', 'created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()', NULL, NULL, NULL),
('COL_PAT_RAW_IS_ACTIVE',   'TBL_PAT_RAW', 'Aktivní',
 'Příznak aktivního pacienta (1 = aktivní, 0 = archivován).', 'BOOLEAN', NULL,
 8, NULL, 'integer', 'is_active BOOLEAN NOT NULL DEFAULT TRUE', NULL, NULL, NULL),
('COL_PAT_RAW_WEIGHT_KG',   'TBL_PAT_RAW', 'Hmotnost (kg)',
 'Tělesná hmotnost pacienta v kilogramech.', 'DECIMAL',
 'http://loinc.org/3141-9', 9, NULL, 'numeric', 'weight_kg DECIMAL(5,2)', NULL, NULL, NULL),
('COL_PAT_RAW_NOTE',        'TBL_PAT_RAW', 'Poznámka',
 'Volný textový komentář ke kartě pacienta.', 'TEXT', NULL,
 10, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_PATIENTS_CLEAN ───────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PAT_CLN', 'DIST_PATIENTS_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.patients_clean',
 'Pacienti (čistá vrstva)', 'Vyčištěná data pacientů s odvozenými sloupci.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PAT_CLN_PATIENT_ID',  'TBL_PAT_CLN', 'ID pacienta',
 'Surrogate klíč pacienta (čistá vrstva).', 'BIGINT', NULL,
 1, 'PK', 'integer', 'patient_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_PAT_CLN_AGE',         'TBL_PAT_CLN', 'Věk (roky)',
 'Věk pacienta k datu extrakce (odvozeno z data narození).', 'INTEGER', NULL,
 2, NULL, 'numeric', 'age_years INTEGER',
 'DATE_PART(''year'', AGE(date_of_birth))', NULL, NULL),
('COL_PAT_CLN_BMI',         'TBL_PAT_CLN', 'BMI',
 'Index tělesné hmotnosti (kg/m²).', 'DECIMAL',
 'http://loinc.org/39156-5', 3, NULL, 'numeric', 'bmi DECIMAL(4,1)',
 'weight_kg / (height_m * height_m)',
 'ROUND(weight_kg / NULLIF(height_m * height_m, 0), 1)',
 'DECIMAL(4,1) GENERATED ALWAYS AS (ROUND(weight_kg / NULLIF(height_m * height_m, 0), 1)) STORED'),
('COL_PAT_CLN_GENDER_CODE', 'TBL_PAT_CLN', 'Kód pohlaví',
 'Kód pohlaví dle číselníku DASTA.', 'VARCHAR',
 'http://snomed.info/sct/263495000', 4, 'FK', 'character', NULL, NULL, NULL, NULL),
('COL_PAT_CLN_ANON_ID',     'TBL_PAT_CLN', 'Anonymizovaný ID',
 'Pseudonymizovaný identifikátor (SHA-256 z rodného čísla).', 'VARCHAR', NULL,
 5, 'UK', 'character', 'anon_id VARCHAR(64) NOT NULL UNIQUE', NULL, NULL, NULL);

-- ── DIST_PATIENTS_ANALYTICAL ──────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PAT_ANA', 'DIST_PATIENTS_ANALYTICAL',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_patient',
 'Dim. pacienti (analytická vrstva)', 'Dimenzionální tabulka pacientů pro star schema.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PAT_ANA_DIM_KEY',    'TBL_PAT_ANA', 'Dimenzní klíč',
 'Surrogate klíč dimenze pacientů (star schema).', 'BIGINT', NULL,
 1, 'PK', 'integer',
 'dim_patient_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY', NULL, NULL, NULL),
('COL_PAT_ANA_SRC_KEY',    'TBL_PAT_ANA', 'Zdrojový klíč',
 'Odkaz na patient_id ve zdrojovém systému.', 'BIGINT', NULL,
 2, 'FK', 'integer', 'src_patient_id BIGINT NOT NULL', NULL, NULL, NULL),
('COL_PAT_ANA_VALID_FROM', 'TBL_PAT_ANA', 'Platnost od',
 'Datum začátku platnosti záznamu (SCD typ 2).', 'DATE', NULL,
 3, NULL, 'Date', 'valid_from DATE NOT NULL', NULL, NULL, NULL),
('COL_PAT_ANA_SEGMENT',    'TBL_PAT_ANA', 'Segment',
 'Marketingový segment pacienta (volný text, bez schématu).', 'TEXT', NULL,
 4, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_LABS_RAW ─────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_LAB_RAW', 'DIST_LABS_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_raw',
 'Laboratorní výsledky (surová vrstva)', 'Surová laboratorní data z LIS systému.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_LAB_RAW_ORDER_ID',   'TBL_LAB_RAW', 'ID objednávky',
 'Identifikátor laboratorní objednávky.', 'BIGINT',
 'http://loinc.org/26436-6', 1, 'PK', 'integer',
 'order_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_LAB_RAW_PATIENT_ID', 'TBL_LAB_RAW', 'ID pacienta',
 'Odkaz na pacienta.', 'INTEGER',
 'http://snomed.info/sct/406547006', 2, 'FK', 'integer',
 'patient_id INTEGER NOT NULL', NULL, NULL, NULL),
('COL_LAB_RAW_TEST_CODE',  'TBL_LAB_RAW', 'Kód testu (LOINC)',
 'LOINC kód laboratorního testu.', 'VARCHAR',
 'http://loinc.org/24357-6', 3, NULL, 'character',
 'test_code VARCHAR(20) NOT NULL', NULL, NULL, NULL),
('COL_LAB_RAW_VALUE_NUM',  'TBL_LAB_RAW', 'Číselná hodnota',
 'Číselný výsledek testu.', 'DECIMAL', NULL,
 4, NULL, 'numeric', 'value_num DECIMAL(12,4)', NULL, NULL, NULL),
('COL_LAB_RAW_RESULT_TS',  'TBL_LAB_RAW', 'Čas výsledku',
 'Časová značka výsledku laboratorního testu.', 'TIMESTAMP', NULL,
 5, NULL, 'POSIXct', 'result_ts TIMESTAMP WITH TIME ZONE', NULL, NULL, NULL);

-- ── DIST_LABS_CLEAN ────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_LAB_CLN', 'DIST_LABS_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.labs_clean',
 'Laboratorní výsledky (čistá vrstva)', 'Vyčištěná laboratorní data s přidanými příznakovými sloupci.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_LAB_CLN_RESULT_ID',   'TBL_LAB_CLN', 'ID výsledku',
 'Identifikátor výsledku (čistá vrstva).', 'BIGINT', NULL,
 1, 'PK', 'integer', 'result_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_LAB_CLN_IS_CRITICAL', 'TBL_LAB_CLN', 'Kritická hodnota',
 'Příznak kritické laboratorní hodnoty.', 'BOOLEAN', NULL,
 2, NULL, 'integer', 'is_critical BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL),
('COL_LAB_CLN_COMMENT',     'TBL_LAB_CLN', 'Komentář',
 'Volný textový komentář k výsledku.', 'TEXT', NULL,
 3, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_RADIOLOGY_NULL_LAYER ─────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_RAD_RAW', 'DIST_RADIOLOGY_NULL_LAYER',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.radiology_raw',
 'Radiologie (vrstva neurčena)', 'DICOM metadata radiologických studií.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_RAD_STUDY_UID',    'TBL_RAD_RAW', 'StudyInstanceUID',
 'Unikátní identifikátor DICOM studie.', 'VARCHAR', NULL,
 1, 'UK', 'character', 'study_instance_uid VARCHAR(128) UNIQUE NOT NULL', NULL, NULL, NULL),
('COL_RAD_SERIES_COUNT', 'TBL_RAD_RAW', 'Počet sérií',
 'Počet sérií v rámci studie.', 'INTEGER', NULL,
 2, NULL, 'integer', 'series_count INTEGER', NULL, NULL, NULL),
('COL_RAD_IMPRESSION',   'TBL_RAD_RAW', 'Závěr',
 'Textový závěr radiologa.', 'TEXT', NULL,
 3, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_PHARMACY_ANALYTICAL ──────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PHR_ANA', 'DIST_PHARMACY_ANALYTICAL',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.dim_medication',
 'Dim. léky (analytická vrstva)', 'Dimenzionální tabulka léků pro analytické dotazy.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PHR_DIM_MED_KEY', 'TBL_PHR_ANA', 'Dimenzní klíč léku',
 'Surrogate klíč dimenze léků.', 'BIGINT', NULL,
 1, 'PK', 'integer',
 'dim_medication_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY', NULL, NULL, NULL),
('COL_PHR_ATC_CODE',    'TBL_PHR_ANA', 'ATC kód',
 'Kód léku dle WHO ATC klasifikace.', 'VARCHAR',
 'http://www.whocc.no/atc', 2, 'UK', 'character',
 'atc_code VARCHAR(10) UNIQUE NOT NULL', NULL, NULL, NULL),
('COL_PHR_DDD',         'TBL_PHR_ANA', 'DDD (mg)',
 'Definovaná denní dávka v mg.', 'DECIMAL',
 'http://www.whocc.no/ddd', 3, NULL, 'numeric',
 'ddd_mg DECIMAL(8,3)', NULL, NULL, NULL);

-- ── DIST_ONCOLOGY_CLEAN ────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_ONC_CLN', 'DIST_ONCOLOGY_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.oncology_clean',
 'Onkologie (čistá vrstva)', 'Vyčištěná onkologická data s diagnózami.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_ONC_DIAGNOSIS_ID', 'TBL_ONC_CLN', 'ID diagnózy',
 'Identifikátor onkologické diagnózy.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'diagnosis_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_ONC_MORPHOLOGY',   'TBL_ONC_CLN', 'Morfologie (ICD-O)',
 'Morfologický kód dle ICD-O klasifikace.', 'VARCHAR',
 'http://snomed.info/sct/400177003', 2, NULL, 'character',
 'morphology_code VARCHAR(10)', NULL, NULL, NULL),
('COL_ONC_DX_DATE',      'TBL_ONC_CLN', 'Datum diagnózy',
 'Datum stanovení onkologické diagnózy.', 'DATE', NULL,
 3, NULL, 'Date', 'diagnosis_date DATE', NULL, NULL, NULL);

-- ── DIST_ADMIN_RAW ─────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_ADM_RAW', 'DIST_ADMIN_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.billing_raw',
 'Administrativa (surová vrstva)', 'Fakturace, pojistné nároky a platby z fakturačního systému.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_ADM_ENCOUNTER_ID', 'TBL_ADM_RAW', 'ID návštěvy',
 'Identifikátor administrativní návštěvy.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'encounter_id BIGINT NOT NULL PRIMARY KEY',
 'seq_encounter.NEXTVAL', 'CAST(seq_encounter.NEXTVAL AS BIGINT)',
 'BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY'),
('COL_ADM_PATIENT_ID',   'TBL_ADM_RAW', 'ID pacienta',
 'Odkaz na pacienta.', 'BIGINT',
 'http://snomed.info/sct/406547006', 2, 'FK', 'integer',
 'patient_id BIGINT NOT NULL', NULL, NULL, NULL),
('COL_ADM_TOTAL_CHARGE', 'TBL_ADM_RAW', 'Celková částka',
 'Celková fakturovaná částka v CZK.', 'DECIMAL', NULL,
 3, NULL, 'numeric', 'total_charge DECIMAL(12,2)', NULL, NULL, NULL),
('COL_ADM_DISCHARGE_TS', 'TBL_ADM_RAW', 'Datum propuštění',
 'Časová značka propuštění pacienta.', 'TIMESTAMP', NULL,
 4, NULL, 'POSIXct', 'discharge_ts TIMESTAMP WITH TIME ZONE', NULL, NULL, NULL),
('COL_ADM_NOTE',         'TBL_ADM_RAW', 'Poznámka k faktuře',
 'Volný textový komentář k fakturaci.', 'TEXT', NULL,
 5, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_ICU_RAW ───────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_ICU_RAW', 'DIST_ICU_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.icu_raw',
 'JIP (surová vrstva)', 'Surová data monitoringu pacientů na jednotce intenzivní péče.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_ICU_RAW_EVENT_ID',    'TBL_ICU_RAW', 'ID události',
 'Identifikátor monitorovacího záznamu JIP.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'event_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_ICU_RAW_PATIENT_ID',  'TBL_ICU_RAW', 'ID pacienta',
 'Odkaz na pacienta.', 'INTEGER',
 'http://snomed.info/sct/406547006', 2, 'FK', 'integer',
 'patient_id INTEGER NOT NULL', NULL, NULL, NULL),
('COL_ICU_RAW_SOFA',        'TBL_ICU_RAW', 'Skóre SOFA',
 'Sekvenční hodnocení selhání orgánů (SOFA).', 'INTEGER',
 'http://loinc.org/97798-0', 3, NULL, 'integer', 'sofa_score INTEGER', NULL, NULL, NULL),
('COL_ICU_RAW_VENTILATED',  'TBL_ICU_RAW', 'Umělá plicní ventilace',
 'Příznak připojení k umělé plicní ventilaci.', 'BOOLEAN', NULL,
 4, NULL, 'integer', 'is_ventilated BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL),
('COL_ICU_RAW_RECORDED_AT', 'TBL_ICU_RAW', 'Čas záznamu',
 'Časová značka záznamu monitorovacích dat.', 'TIMESTAMP', NULL,
 5, NULL, 'POSIXct', 'recorded_at TIMESTAMP WITH TIME ZONE NOT NULL', NULL, NULL, NULL);

-- ── DIST_ICU_CLEAN ─────────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_ICU_CLN', 'DIST_ICU_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.icu_clean',
 'JIP (čistá vrstva)', 'Vyčištěná data JIP s odvozenými ukazateli.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_ICU_CLN_STAY_ID',    'TBL_ICU_CLN', 'ID pobytu',
 'Identifikátor pobytu na JIP.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'stay_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_ICU_CLN_LOS_HOURS',  'TBL_ICU_CLN', 'Délka pobytu (hod)',
 'Délka pobytu na JIP v hodinách.', 'DECIMAL', NULL,
 2, NULL, 'numeric', 'los_hours DECIMAL(8,2)', NULL, NULL, NULL),
('COL_ICU_CLN_MORTALITY',  'TBL_ICU_CLN', 'Mortalita',
 'Příznak úmrtí na JIP.', 'BOOLEAN', NULL,
 3, NULL, 'integer', 'in_hospital_death BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL);

-- ── DIST_SURGERY_RAW ───────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_SRG_RAW', 'DIST_SURGERY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.surgery_raw',
 'Chirurgie (surová vrstva)', 'Surová data operačních záznamů z nemocničního informačního systému.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_SRG_OP_ID',        'TBL_SRG_RAW', 'ID operace',
 'Identifikátor operačního záznamu.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'operation_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_SRG_ICD_CODE',     'TBL_SRG_RAW', 'Kód výkonu (ICD-9-CM)',
 'Kód chirurgického výkonu dle ICD-9-CM.', 'VARCHAR',
 'http://snomed.info/sct/387713003', 2, NULL, 'character',
 'procedure_code VARCHAR(20)', NULL, NULL, NULL),
('COL_SRG_DURATION_MIN', 'TBL_SRG_RAW', 'Délka operace (min)',
 'Délka operace v minutách.', 'INTEGER', NULL,
 3, NULL, 'integer', 'duration_minutes INTEGER', NULL, NULL, NULL),
('COL_SRG_COMPLICATION', 'TBL_SRG_RAW', 'Komplikace',
 'Textový popis komplikace operace.', 'TEXT', NULL,
 4, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_CARDIOLOGY_RAW ────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_CAR_RAW', 'DIST_CARDIOLOGY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.cardiology_raw',
 'Kardiologie (surová vrstva)', 'Surová kardiologická data z EKG a echokardiografie.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_CAR_EXAM_ID',    'TBL_CAR_RAW', 'ID vyšetření',
 'Identifikátor kardiologického vyšetření.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'exam_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_CAR_HR_BPM',     'TBL_CAR_RAW', 'Srdeční frekvence (bpm)',
 'Srdeční frekvence v tepech za minutu.', 'INTEGER',
 'http://loinc.org/8867-4', 2, NULL, 'integer', 'heart_rate_bpm INTEGER', NULL, NULL, NULL),
('COL_CAR_EJECTION_F', 'TBL_CAR_RAW', 'Ejekční frakce (%)',
 'Ejekční frakce levé komory v procentech.', 'DECIMAL',
 'http://loinc.org/10230-1', 3, NULL, 'numeric', 'ejection_fraction DECIMAL(5,2)', NULL, NULL, NULL),
('COL_CAR_RHYTHM',     'TBL_CAR_RAW', 'Srdeční rytmus',
 'Popis srdečního rytmu (sinusový, fibrilace síní, aj.).', 'VARCHAR', NULL,
 4, NULL, 'character', 'rhythm_description VARCHAR(100)', NULL, NULL, NULL);

-- ── DIST_CARDIOLOGY_ANALYTICAL ────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_CAR_ANA', 'DIST_CARDIOLOGY_ANALYTICAL',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.fact_cardiology',
 'Kardiologie (analytická vrstva)', 'Faktová tabulka kardiologických vyšetření pro star schema.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_CAR_ANA_FACT_KEY',  'TBL_CAR_ANA', 'Faktový klíč',
 'Surrogate klíč faktu kardiologického vyšetření.', 'BIGINT', NULL,
 1, 'PK', 'integer',
 'fact_cardiology_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY', NULL, NULL, NULL),
('COL_CAR_ANA_DIM_PATIENT','TBL_CAR_ANA', 'Dim. klíč pacienta',
 'Odkaz na dimenzi pacientů.', 'BIGINT', NULL,
 2, 'FK', 'integer', 'dim_patient_key BIGINT NOT NULL', NULL, NULL, NULL),
('COL_CAR_ANA_RISK_SCORE', 'TBL_CAR_ANA', 'Kardiovaskulární riziko',
 'Skóre kardiovaskulárního rizika.', 'DECIMAL', NULL,
 3, NULL, 'numeric', 'cv_risk_score DECIMAL(5,2)', NULL, NULL, NULL);

-- ── DIST_NEUROLOGY_RAW ─────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_NEU_RAW', 'DIST_NEUROLOGY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.neurology_raw',
 'Neurologie (surová vrstva)', 'Surová neurologická data z EEG a zobrazovacích metod.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_NEU_RECORD_ID', 'TBL_NEU_RAW', 'ID záznamu',
 'Identifikátor neurologického záznamu.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'record_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_NEU_SCORE_GCS', 'TBL_NEU_RAW', 'Skóre GCS',
 'Glasgow Coma Scale – hodnocení vědomí.', 'INTEGER',
 'http://loinc.org/35088-4', 2, NULL, 'integer', 'score_gcs INTEGER', NULL, NULL, NULL),
('COL_NEU_EEG_FINDING','TBL_NEU_RAW', 'Nález EEG',
 'Textový popis nálezu EEG.', 'TEXT', NULL,
 3, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_PATHOLOGY_RAW ─────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PAT2_RAW', 'DIST_PATHOLOGY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.pathology_raw',
 'Patologie (surová vrstva)', 'Surová histopatologická data z patologie.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PAT2_BLOCK_ID',  'TBL_PAT2_RAW', 'ID parafinového bloku',
 'Identifikátor parafinového bloku tkáňového vzorku.', 'VARCHAR', NULL,
 1, 'PK', 'character', 'block_id VARCHAR(30) NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_PAT2_STAIN',     'TBL_PAT2_RAW', 'Typ barvení',
 'Typ histochemického barvení (HE, PAS, apod.).', 'VARCHAR', NULL,
 2, NULL, 'character', 'stain_type VARCHAR(20)', NULL, NULL, NULL),
('COL_PAT2_DIAGNOSIS', 'TBL_PAT2_RAW', 'Diagnóza (text)',
 'Volný textový závěr patologa.', 'TEXT', NULL,
 3, NULL, 'character', NULL, NULL, NULL, NULL);

-- ── DIST_MICROBIOLOGY_RAW ──────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_MIC_RAW', 'DIST_MICROBIOLOGY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.microbiology_raw',
 'Mikrobiologie (surová vrstva)', 'Surová mikrobiologická data kultivací a citlivostí.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_MIC_SAMPLE_ID',   'TBL_MIC_RAW', 'ID vzorku',
 'Identifikátor mikrobiologického vzorku.', 'VARCHAR', NULL,
 1, 'PK', 'character', 'sample_id VARCHAR(30) NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_MIC_ORGANISM',    'TBL_MIC_RAW', 'Organismus',
 'Identifikovaný mikroorganismus (SNOMED CT).', 'VARCHAR',
 'http://snomed.info/sct/409822003', 2, NULL, 'character',
 'organism_code VARCHAR(20)', NULL, NULL, NULL),
('COL_MIC_SENSITIVITY', 'TBL_MIC_RAW', 'Citlivost',
 'Výsledek testu citlivosti na antibiotika (S/I/R).', 'VARCHAR', NULL,
 3, NULL, 'character', 'sensitivity_result VARCHAR(1)', NULL, NULL, NULL),
('COL_MIC_ANTIBIOTIC',  'TBL_MIC_RAW', 'Antibiotikum',
 'Název testovaného antibiotika.', 'VARCHAR', NULL,
 4, NULL, 'character', 'antibiotic_name VARCHAR(100)', NULL, NULL, NULL);

-- ── DIST_EMERGENCY_RAW ─────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_EMR_RAW', 'DIST_EMERGENCY_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.emergency_raw',
 'Urgentní příjem (surová vrstva)', 'Surová data urgentního příjmu z triážního systému.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_EMR_VISIT_ID',  'TBL_EMR_RAW', 'ID návštěvy',
 'Identifikátor návštěvy urgentního příjmu.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'visit_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_EMR_TRIAGE_LVL','TBL_EMR_RAW', 'Triážní stupeň (MTS)',
 'Triážní stupeň dle Manchester Triage System (1-5).', 'INTEGER', NULL,
 2, NULL, 'integer', 'triage_level INTEGER NOT NULL', NULL, NULL, NULL),
('COL_EMR_CHIEF_CMPL', 'TBL_EMR_RAW', 'Hlavní stížnost',
 'Hlavní stížnost pacienta při přijetí na urgentní příjem.', 'TEXT', NULL,
 3, NULL, 'character', NULL, NULL, NULL, NULL),
('COL_EMR_DISPOSITION','TBL_EMR_RAW', 'Dispozice',
 'Výsledná dispozice pacienta (hospitalizace, propuštění, překlad).', 'VARCHAR', NULL,
 4, NULL, 'character', 'disposition VARCHAR(50)', NULL, NULL, NULL);

-- ── DIST_PSYCHIATRY_CLEAN ──────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PSY_CLN', 'DIST_PSYCHIATRY_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.psychiatry_clean',
 'Psychiatrie (čistá vrstva)', 'Vyčištěná psychiatrická data s pseudonymizovanými identifikátory.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PSY_EPISODE_ID',  'TBL_PSY_CLN', 'ID epizody',
 'Identifikátor psychiatrické epizody.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'episode_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_PSY_DIAGNOSIS',   'TBL_PSY_CLN', 'Diagnóza (MKN-10)',
 'Psychiatrická diagnóza dle MKN-10.', 'VARCHAR',
 'http://snomed.info/sct/73211009', 2, NULL, 'character',
 'diagnosis_code VARCHAR(10)', NULL, NULL, NULL),
('COL_PSY_GAF_SCORE',   'TBL_PSY_CLN', 'Skóre GAF',
 'Globální hodnocení funkčnosti (GAF, 0-100).', 'INTEGER', NULL,
 3, NULL, 'integer', 'gaf_score INTEGER', NULL, NULL, NULL),
('COL_PSY_MEDICATION',  'TBL_PSY_CLN', 'Psychofarmaka',
 'Název předepsaného psychofarmaka.', 'VARCHAR', NULL,
 4, NULL, 'character', 'medication_name VARCHAR(200)', NULL, NULL, NULL);

-- ── DIST_PEDIATRICS_RAW ────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_PED_RAW', 'DIST_PEDIATRICS_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.pediatrics_raw',
 'Pediatrie (surová vrstva)', 'Surová pediatrická data včetně růstových parametrů.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_PED_VISIT_ID', 'TBL_PED_RAW', 'ID návštěvy',
 'Identifikátor pediatrické návštěvy.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'visit_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_PED_HEIGHT_CM','TBL_PED_RAW', 'Výška (cm)',
 'Výška dítěte v centimetrech.', 'DECIMAL',
 'http://loinc.org/8302-2', 2, NULL, 'numeric', 'height_cm DECIMAL(5,1)', NULL, NULL, NULL),
('COL_PED_WEIGHT_KG','TBL_PED_RAW', 'Hmotnost (kg)',
 'Hmotnost dítěte v kilogramech.', 'DECIMAL',
 'http://loinc.org/29463-7', 3, NULL, 'numeric', 'weight_kg DECIMAL(5,2)', NULL, NULL, NULL),
('COL_PED_VACC_STATUS','TBL_PED_RAW', 'Stav očkování',
 'Stav očkování dítěte (kompletní / neúplné / nezahájeno).', 'VARCHAR', NULL,
 4, NULL, 'character', 'vaccination_status VARCHAR(20)', NULL, NULL, NULL);

-- ── DIST_VITAL_SIGNS_RAW ───────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_VIT_RAW', 'DIST_VITAL_SIGNS_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.vital_signs_raw',
 'Vitální funkce (surová vrstva)', 'Kontinuální záznamy vitálních funkcí z bedside monitorů.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_VIT_READING_ID', 'TBL_VIT_RAW', 'ID záznamu',
 'Identifikátor záznamu vitálních funkcí.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'reading_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_VIT_SBP_MMHG',  'TBL_VIT_RAW', 'Systolický TK (mmHg)',
 'Systolický krevní tlak v mmHg.', 'INTEGER',
 'http://loinc.org/8480-6', 2, NULL, 'integer', 'sbp_mmhg INTEGER', NULL, NULL, NULL),
('COL_VIT_DBP_MMHG',  'TBL_VIT_RAW', 'Diastolický TK (mmHg)',
 'Diastolický krevní tlak v mmHg.', 'INTEGER',
 'http://loinc.org/8462-4', 3, NULL, 'integer', 'dbp_mmhg INTEGER', NULL, NULL, NULL),
('COL_VIT_SPO2',      'TBL_VIT_RAW', 'SpO2 (%)',
 'Saturace kyslíkem (pulzní oxymetrie) v procentech.', 'DECIMAL',
 'http://loinc.org/59408-5', 4, NULL, 'numeric', 'spo2_pct DECIMAL(5,2)', NULL, NULL, NULL),
('COL_VIT_TEMP_C',    'TBL_VIT_RAW', 'Tělesná teplota (°C)',
 'Tělesná teplota v stupních Celsia.', 'DECIMAL',
 'http://loinc.org/8310-5', 5, NULL, 'numeric', 'temp_celsius DECIMAL(4,1)', NULL, NULL, NULL),
('COL_VIT_RECORDED_AT','TBL_VIT_RAW', 'Čas záznamu',
 'Časová značka záznamu vitálních funkcí.', 'TIMESTAMP', NULL,
 6, NULL, 'POSIXct', 'recorded_at TIMESTAMP WITH TIME ZONE NOT NULL', NULL, NULL, NULL);

-- ── DIST_GENOMICS_RAW ──────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_GEN_RAW', 'DIST_GENOMICS_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.genomics_raw',
 'Genomika (surová vrstva)', 'Surová genomická data z NGS sekvenování.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_GEN_SAMPLE_ID',   'TBL_GEN_RAW', 'ID vzorku',
 'Identifikátor genomického vzorku.', 'VARCHAR', NULL,
 1, 'PK', 'character', 'sample_id VARCHAR(50) NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_GEN_VARIANT_ID',  'TBL_GEN_RAW', 'ID varianty',
 'Identifikátor genomické varianty (rsID / ClinVar).', 'VARCHAR', NULL,
 2, 'UK', 'character', 'variant_id VARCHAR(50) NOT NULL', NULL, NULL, NULL),
('COL_GEN_CHROMOSOME',  'TBL_GEN_RAW', 'Chromozóm',
 'Číslo chromozómu obsahujícího variantu.', 'VARCHAR', NULL,
 3, NULL, 'character', 'chromosome VARCHAR(5)', NULL, NULL, NULL),
('COL_GEN_POSITION',    'TBL_GEN_RAW', 'Genomická poloha',
 'Genomická poloha varianty (GRCh38).', 'INTEGER', NULL,
 4, NULL, 'integer', 'genomic_position INTEGER', NULL, NULL, NULL),
('COL_GEN_ZYGOSITY',    'TBL_GEN_RAW', 'Zygozita',
 'Zygozita varianty (homozygotní / heterozygotní).', 'VARCHAR', NULL,
 5, NULL, 'character', 'zygosity VARCHAR(15)', NULL, NULL, NULL);

-- ── DIST_REHABILITATION_CLEAN ──────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_REH_CLN', 'DIST_REHABILITATION_CLEAN',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.rehabilitation_clean',
 'Rehabilitace (čistá vrstva)', 'Vyčištěná data rehabilitačních plánů a výsledků.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_REH_PLAN_ID',   'TBL_REH_CLN', 'ID plánu',
 'Identifikátor rehabilitačního plánu.', 'BIGINT', NULL,
 1, 'PK', 'integer', 'plan_id BIGINT NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_REH_THERAPY_TYPE','TBL_REH_CLN', 'Typ terapie',
 'Typ rehabilitační terapie (fyzio, ergo, logopedie, aj.).', 'VARCHAR', NULL,
 2, NULL, 'character', 'therapy_type VARCHAR(50)', NULL, NULL, NULL),
('COL_REH_FIM_SCORE',  'TBL_REH_CLN', 'Skóre FIM',
 'Funkční index nezávislosti (Functional Independence Measure).', 'INTEGER', NULL,
 3, NULL, 'integer', 'fim_score INTEGER', NULL, NULL, NULL),
('COL_REH_GOAL_MET',   'TBL_REH_CLN', 'Splnění cíle',
 'Příznak dosažení rehabilitačního cíle.', 'BOOLEAN', NULL,
 4, NULL, 'integer', 'goal_met BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL);

-- ── DIST_DIET_NUTRITION_ANALYTICAL ────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_DIT_ANA', 'DIST_DIET_NUTRITION_ANALYTICAL',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.fact_nutrition',
 'Výživa a dieta (analytická vrstva)', 'Faktová tabulka nutričních plánů a kalorických příjmů.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_DIT_FACT_KEY',    'TBL_DIT_ANA', 'Faktový klíč',
 'Surrogate klíč faktu nutričního záznamu.', 'BIGINT', NULL,
 1, 'PK', 'integer',
 'fact_nutrition_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY', NULL, NULL, NULL),
('COL_DIT_DIET_TYPE',   'TBL_DIT_ANA', 'Typ diety',
 'Kód dietetické specifikace (standardní, bezlaktózová, aj.).', 'VARCHAR', NULL,
 2, NULL, 'character', 'diet_type_code VARCHAR(20)', NULL, NULL, NULL),
('COL_DIT_KCAL',        'TBL_DIT_ANA', 'Kalorický příjem (kcal)',
 'Celkový kalorický příjem za den v kcal.', 'DECIMAL',
 'http://loinc.org/9052-2', 3, NULL, 'numeric', 'total_kcal DECIMAL(8,2)', NULL, NULL, NULL),
('COL_DIT_PROTEIN_G',   'TBL_DIT_ANA', 'Bílkoviny (g)',
 'Příjem bílkovin za den v gramech.', 'DECIMAL',
 'http://loinc.org/56099-3', 4, NULL, 'numeric', 'protein_g DECIMAL(7,2)', NULL, NULL, NULL);

-- ── DIST_IMAGING_CT_RAW ────────────────────────────────────────
INSERT INTO metadata."lm_table" (name, distribution_name, url, title, description) VALUES
('TBL_CT_RAW', 'DIST_IMAGING_CT_RAW',
 'jdbc:postgresql://dwh-db:5432/dwh/metadata.imaging_ct_raw',
 'CT zobrazení (surová vrstva)', 'Surová metadata CT vyšetření z PACS systému.');

INSERT INTO metadata."lm_column" (
    name, table_name, title, description, datatype,
    property_url, var_order, key_db, type_r,
    definition_ddl, definition_pk_pom1, definition_pk_pom2, definition_pk
) VALUES
('COL_CT_STUDY_ID',    'TBL_CT_RAW', 'ID studie',
 'Identifikátor CT studie v PACS systému.', 'VARCHAR', NULL,
 1, 'PK', 'character', 'study_id VARCHAR(64) NOT NULL PRIMARY KEY', NULL, NULL, NULL),
('COL_CT_BODY_PART',   'TBL_CT_RAW', 'Oblast těla',
 'Oblast těla zobrazená CT vyšetřením (SNOMED CT).', 'VARCHAR',
 'http://snomed.info/sct/38866009', 2, NULL, 'character',
 'body_part_code VARCHAR(30)', NULL, NULL, NULL),
('COL_CT_SLICE_COUNT', 'TBL_CT_RAW', 'Počet řezů',
 'Počet axiálních řezů v CT sérii.', 'INTEGER', NULL,
 3, NULL, 'integer', 'slice_count INTEGER', NULL, NULL, NULL),
('COL_CT_CONTRAST',    'TBL_CT_RAW', 'Kontrast',
 'Příznak podání kontrastní látky.', 'BOOLEAN', NULL,
 4, NULL, 'integer', 'contrast_used BOOLEAN NOT NULL DEFAULT FALSE', NULL, NULL, NULL),
('COL_CT_IMPRESSION',  'TBL_CT_RAW', 'Závěr CT',
 'Volný textový závěr radiologa k CT vyšetření.', 'TEXT', NULL,
 5, NULL, 'character', NULL, NULL, NULL, NULL);
