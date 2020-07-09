#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE DATABASE test_historian;
    \c test_historian

	CREATE TABLE data (
    ts TIMESTAMP NOT NULL,
    topic_id INTEGER NOT NULL,
    value_string TEXT NOT NULL,
    UNIQUE (topic_id, ts));
    INSERT INTO data VALUES ('2020-06-01 12:30:59', 13, '[2,3]');
    INSERT INTO data VALUES ('2020-06-01 06:30:59', 42, '2');
    INSERT INTO data VALUES ('2020-06-01 12:31:59', 43, '8');

    CREATE TABLE IF NOT EXISTS topics (
    topic_id SERIAL PRIMARY KEY NOT NULL,
    topic_name VARCHAR(512) NOT NULL,
    UNIQUE (topic_name));
    INSERT INTO topics (topic_name) VALUES ('football');
    INSERT INTO topics (topic_name) VALUES ('baseball');
    INSERT INTO topics (topic_name) VALUES ('foobar');
    INSERT INTO topics (topic_name) VALUES ('xctljglfkjsgfklsd');

    CREATE TABLE IF NOT EXISTS meta (
    topic_id INTEGER PRIMARY KEY NOT NULL,
    metadata TEXT NOT NULL);

    CREATE TABLE metadata
    (table_id VARCHAR(512) PRIMARY KEY NOT NULL,
    table_name VARCHAR(512) NOT NULL);
    INSERT INTO metadata VALUES ('data_table', 'data');
    INSERT INTO metadata VALUES ('topics_table', 'topics');
    INSERT INTO metadata VALUES ('meta_table', 'meta');

    CREATE TABLE IF NOT EXISTS aggregate_topics (
    agg_topic_id SERIAL PRIMARY KEY NOT NULL,
    agg_topic_name VARCHAR(512) NOT NULL,
    agg_type VARCHAR(512) NOT NULL,
    agg_time_period VARCHAR(512) NOT NULL,
    UNIQUE (agg_topic_name, agg_type, agg_time_period));
    INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period) VALUES ('some_agg_topic', 'AVG', '2019');

    CREATE TABLE IF NOT EXISTS aggregate_meta (
    agg_topic_id INTEGER PRIMARY KEY NOT NULL,
    metadata TEXT NOT NULL);
    INSERT INTO aggregate_meta VALUES (1, '{"configured_topics": "meaning of life"}');

    CREATE TABLE avg_1776 (
    ts timestamp NOT NULL,
    topic_id INTEGER NOT NULL,
    value_string TEXT NOT NULL,
    topics_list TEXT,
    UNIQUE(ts, topic_id));
    CREATE INDEX IF NOT EXISTS idx_avg_1776 ON avg_1776 (ts ASC);

    GRANT ALL PRIVILEGES ON DATABASE test_historian TO postgres;
EOSQL
