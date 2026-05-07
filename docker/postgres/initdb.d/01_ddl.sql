-- ============================================================
-- Local Metadata HealthDCAT-AP Schema  (lm_* tables)
-- ============================================================
-- Runs once on first Postgres container start via initdb.d/.
-- Matches warehouse/models.py (managed=False).
--
-- FK naming follows Django defaults:
--   ForeignKey field "foo" without db_column -> column "foo_id"
--   ForeignKey field "bar" with db_column='bar' -> column "bar"
-- ============================================================

CREATE SCHEMA IF NOT EXISTS metadata;

-- -- 1. ContactPoint -----------------------------------------
-- Maps to warehouse.ContactPoint / shared.ContactPointBase
-- Both fields are nullable: a ContactPoint may carry
-- email only, page only, both, or neither.
CREATE TABLE IF NOT EXISTS metadata."lm_contact_point" (
    id           BIGSERIAL    PRIMARY KEY,
    email        VARCHAR(255),           -- vcard:email (nullable)
    contact_page VARCHAR(500)            -- vcard:hasURL (nullable)
);

-- -- 2. Agent -------------------------------------------------
-- Maps to warehouse.Agent / shared.AgentBase
-- name is the natural key / PK throughout the catalogue.
CREATE TABLE IF NOT EXISTS metadata."lm_agent" (
    name              VARCHAR(255) PRIMARY KEY,
    contact_point_id  BIGINT REFERENCES metadata."lm_contact_point"(id)
                           ON DELETE SET NULL,
    description       TEXT                    -- dct:description (optional)
);

-- -- 3. Catalog -----------------------------------------------
-- Maps to warehouse.Catalog / shared.CatalogBase
-- applicable_legislation is mandatory (HealthDCAT-AP v6 section 4.2).
CREATE TABLE IF NOT EXISTS metadata."lm_catalog" (
    name                   VARCHAR(255) PRIMARY KEY,
    title                  VARCHAR(500),
    description            TEXT,
    publisher_id           VARCHAR(255) REFERENCES metadata."lm_agent"(name)
                               ON DELETE SET NULL,
    applicable_legislation VARCHAR(500) NOT NULL
);

-- -- 4. Dataset -----------------------------------------------
-- Maps to warehouse.Dataset / shared.DatasetBase
-- Mandatory HealthDCAT-AP v6 fields:
--   access_rights, applicable_legislation, health_category, hdab_id.
CREATE TABLE IF NOT EXISTS metadata."lm_dataset" (
    name                   VARCHAR(255) PRIMARY KEY,
    title                  VARCHAR(500),
    version                VARCHAR(100),
    description            TEXT,
    theme                  VARCHAR(500),           -- dcat:theme URI
    publisher_id           VARCHAR(255) REFERENCES metadata."lm_agent"(name)
                               ON DELETE SET NULL,
    identifier             VARCHAR(500) NOT NULL DEFAULT '',  -- dct:identifier URI
    type                   VARCHAR(500) NOT NULL DEFAULT '',  -- dct:type URI
    conforms_to            VARCHAR(500),           -- dct:conformsTo URI
    issued                 TIMESTAMPTZ,            -- dct:issued
    modified               TIMESTAMPTZ,            -- dct:modified
    keyword                TEXT,                   -- dcat:keyword (comma-sep)
    source                 VARCHAR(255)            -- dct:source FK -> lm_dataset.name
                               REFERENCES metadata."lm_dataset"(name)
                               ON DELETE SET NULL,
    creator                VARCHAR(255)            -- dct:creator FK -> lm_agent.name
                               REFERENCES metadata."lm_agent"(name)
                               ON DELETE SET NULL,
    contact_point_id       BIGINT NOT NULL             -- dcat:contactPoint (mandatory)
                               REFERENCES metadata."lm_contact_point"(id)
                               ON DELETE RESTRICT,
    provenance             TEXT,                   -- dct:provenance
    catalog_id             VARCHAR(255) REFERENCES metadata."lm_catalog"(name)
                               ON DELETE SET NULL,
    -- Mandatory HealthDCAT-AP v6
    access_rights          VARCHAR(500) NOT NULL,  -- dct:accessRights
    applicable_legislation VARCHAR(500) NOT NULL,  -- dct:applicableLegislation
    health_category        VARCHAR(500) NOT NULL,  -- healthdcat:healthCategory
    hdab_id                VARCHAR(255) NOT NULL   -- healthdcat:hdab
                               REFERENCES metadata."lm_agent"(name)
                               ON DELETE RESTRICT,
    custodian_id           VARCHAR(255)            -- geodcatap:custodian (optional)
                               REFERENCES metadata."lm_agent"(name)
                               ON DELETE SET NULL
);

-- -- 5. Distribution ------------------------------------------
-- Maps to warehouse.Distribution / shared.DistributionBase
-- + db_layer (LM-specific DWH layer: raw / clean / analytical / NULL).
-- dataset_name uses explicit db_column (to_field='name' in Django model).
CREATE TABLE IF NOT EXISTS metadata."lm_distribution" (
    name                   VARCHAR(255) PRIMARY KEY,
    dataset_name           VARCHAR(255) NOT NULL   -- FK with explicit db_column
                               REFERENCES metadata."lm_dataset"(name)
                               ON DELETE CASCADE,
    title                  VARCHAR(500),
    description            TEXT,
    format                 VARCHAR(100),            -- dct:format
    conforms_to            VARCHAR(500),
    byte_size              INTEGER,                 -- dcat:byteSize
    rights                 VARCHAR(500),            -- dct:rights
    release_date           TIMESTAMPTZ,            -- dct:issued
    modification_date      TIMESTAMPTZ,            -- dct:modified
    -- Mandatory HealthDCAT-AP v6
    access_url             VARCHAR(500) NOT NULL,  -- dcat:accessURL
    applicable_legislation VARCHAR(500) NOT NULL,
    licence                VARCHAR(500),           -- dct:license URI
    -- LM-specific
    db_layer               VARCHAR(100)            -- DWH layer (raw/clean/analytical)
);

-- -- 6. Table -------------------------------------------------
-- Maps to warehouse.Table.  Links a Distribution to its physical DB table.
-- distribution_name uses explicit db_column (to_field='name' in Django model).
CREATE TABLE IF NOT EXISTS metadata."lm_table" (
    name              VARCHAR(255) PRIMARY KEY,
    distribution_name VARCHAR(255) NOT NULL   -- FK with explicit db_column
                          REFERENCES metadata."lm_distribution"(name)
                          ON DELETE CASCADE,
    url               VARCHAR(500) NOT NULL,  -- csvw:url (mandatory)
    title             VARCHAR(500),           -- csvw:title (optional)
    description       TEXT                    -- dct:description (optional)
);

-- -- 7. Column ------------------------------------------------
-- Maps to warehouse.Column (no abstract base - LM-specific only).
-- Describes individual columns within a physical DB table.
-- table_name uses explicit db_column (to_field='name' in Django model).
CREATE TABLE IF NOT EXISTS metadata."lm_column" (
    name               VARCHAR(255) PRIMARY KEY,
    table_name         VARCHAR(255) NOT NULL   -- FK with explicit db_column
                           REFERENCES metadata."lm_table"(name)
                           ON DELETE CASCADE,
    title              VARCHAR(500) NOT NULL,  -- csvw:title (mandatory)
    description        TEXT         NOT NULL,  -- dct:description (mandatory)
    datatype           VARCHAR(100) NOT NULL,  -- csvw:datatype (mandatory)
    property_url       VARCHAR(500),           -- csvw:propertyUrl (optional)
    var_order          SMALLINT,               -- position in source table
    key_db             VARCHAR(100),           -- PK / FK / UK / NULL
    type_r             VARCHAR(50),            -- R datatype (character/integer ...)
    definition_ddl     TEXT,                   -- full DDL column definition
    definition_pk_pom1 TEXT,                   -- PK derivation helper 1
    definition_pk_pom2 TEXT,                   -- PK derivation helper 2
    definition_pk      TEXT                    -- PK definition expression
);
