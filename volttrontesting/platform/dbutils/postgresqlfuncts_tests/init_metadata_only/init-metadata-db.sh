#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE DATABASE test_historian;
    \c test_historian

    CREATE TABLE metadata
    (table_id VARCHAR(512) PRIMARY KEY NOT NULL,
    table_name VARCHAR(512) NOT NULL);
    INSERT INTO metadata VALUES ('data_table', 'data');
    INSERT INTO metadata VALUES ('topics_table', 'topics');
    INSERT INTO metadata VALUES ('meta_table', 'meta');

    GRANT ALL PRIVILEGES ON DATABASE test_historian TO postgres;
EOSQL
