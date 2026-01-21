-- DROP SCHEMA metadata;

CREATE SCHEMA metadata;
-- metadata.datasource_list definition

-- Drop table

-- DROP TABLE metadata.datasource_list;

CREATE TABLE metadata.datasource_list (
	data_source varchar(50) NOT NULL,
	data_source_name varchar(255) NULL,
	subject varchar(255) NULL,
	description text NULL,
	CONSTRAINT xpk_datasource_list PRIMARY KEY (data_source)
);


-- metadata.dataset_list definition

-- Drop table

-- DROP TABLE metadata.dataset_list;

CREATE TABLE metadata.dataset_list (
	data_source varchar(50) NULL,
	data_set varchar(100) NOT NULL,
	data_set_name varchar(255) NULL,
	subject varchar(255) NULL,
	description text NULL,
	author varchar(100) NULL,
	contributor varchar(100) NULL,
	publisher varchar(100) NULL,
	rights_holder varchar(100) NULL,
	provenance text NULL,
	complete varchar(3) NULL,
	CONSTRAINT xpk_dataset_list PRIMARY KEY (data_set),
	CONSTRAINT fk_source FOREIGN KEY (data_source) REFERENCES metadata.datasource_list(data_source) ON DELETE RESTRICT ON UPDATE CASCADE
);


-- metadata.dataclass_list definition

-- Drop table

-- DROP TABLE metadata.dataclass_list;

CREATE TABLE metadata.dataclass_list (
	data_set varchar(100) NULL,
	data_class varchar(100) NOT NULL,
	data_class_name varchar(255) NULL,
	subject varchar(255) NULL,
	description text NULL,
	file_extension varchar(50) NULL,
	resource_type varchar(50) NULL,
	resource_content varchar(50) NULL,
	data_confidentality varchar(100) NULL,
	language_code varchar(50) NULL,
	provenance text NULL,
	data_quality varchar(100) NULL,
	repository varchar(5) NULL,
	complete varchar(5) NULL,
	etl varchar(5) NULL,
	CONSTRAINT xpk_dataclass_list PRIMARY KEY (data_class),
	CONSTRAINT fk_dataset FOREIGN KEY (data_set) REFERENCES metadata.dataset_list(data_set) ON DELETE RESTRICT ON UPDATE CASCADE
);


-- metadata.dataclass_table_schemes definition

-- Drop table

-- DROP TABLE metadata.dataclass_table_schemes;

CREATE TABLE metadata.dataclass_table_schemes (
	data_class varchar(100) NOT NULL,
	col_order int2 NOT NULL,
	col_var varchar(100) NULL,
	col_name varchar(255) NULL,
	col_description text NULL,
	col_var_r varchar(100) NULL,
	col_transf_r int2 NULL,
	datatype_r varchar(20) NULL,
	possible_key varchar(100) NULL,
	tag varchar(100) NULL,
	confidentality int2 NULL,
	vocabulary text NULL,
	calculated int2 NULL,
	madatory int2 NULL,
	unit varchar(20) NULL,
	CONSTRAINT xpk_dataclass_table_schemes PRIMARY KEY (data_class, col_order),
	CONSTRAINT fk_dataclass_desc FOREIGN KEY (data_class) REFERENCES metadata.dataclass_list(data_class) ON DELETE RESTRICT ON UPDATE CASCADE
);


-- metadata.db_table_list definition

-- Drop table

-- DROP TABLE metadata.db_table_list;

CREATE TABLE metadata.db_table_list (
	data_class varchar(100) NULL,
	db_layer varchar(50) NULL,
	db_table varchar(100) NOT NULL,
	db_table_name varchar(255) NULL,
	description text NULL,
	datetime_created date NULL,
	datetime_last_modified date NULL,
	CONSTRAINT xpk_db_table_list PRIMARY KEY (db_table),
	CONSTRAINT fk_dataclass FOREIGN KEY (data_class) REFERENCES metadata.dataclass_list(data_class) ON DELETE RESTRICT ON UPDATE CASCADE
);


-- metadata.db_table_schemes definition

-- Drop table

-- DROP TABLE metadata.db_table_schemes;

CREATE TABLE metadata.db_table_schemes (
	db_table varchar(100) NOT NULL,
	var_order int2 NULL,
	var varchar(100) NOT NULL,
	key_db varchar(100) NULL,
	type_db varchar(20) NULL,
	type_r varchar(20) NULL,
	var_name varchar(255) NULL,
	var_description text NULL,
	vocabulary text NULL,
	CONSTRAINT xpk_db_table_schemes PRIMARY KEY (db_table, var),
	CONSTRAINT fk_dbtable FOREIGN KEY (db_table) REFERENCES metadata.db_table_list(db_table) ON DELETE RESTRICT ON UPDATE CASCADE
);