-- This script assumes that the user has access to create the database.
-- update database name, user name, and password before executing the below commands
-- table names used below are default names used by historian. If you would like to customize table names
-- customize using the configuration tables_def and change the names in the below commands

CREATE DATABASE test_historian;

USE test_historian;

CREATE TABLE data (ts timestamp(6) NOT NULL,
                                 topic_id INTEGER NOT NULL,
                                 value_string TEXT NOT NULL,
                                 UNIQUE(ts, topic_id));

CREATE INDEX data_idx ON data (ts ASC);

-- From SQLHistorian 4.0.0 metadata is by default stored in topics

CREATE TABLE topics (topic_id INTEGER NOT NULL AUTO_INCREMENT,
                     topic_name varchar(512) NOT NULL,
                     metadata TEXT NOT NULL,
                     PRIMARY KEY (topic_id),
                     UNIQUE(topic_name));

CREATE TABLE volttron_table_definitions(
    table_id varchar(512) PRIMARY KEY,
    table_name varchar(512) NOT NULL,
    table_prefix varchar(512));


-- Use the below syntax for creating user and grant access to the historian database

-- CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';
CREATE USER 'historian'@'localhost' IDENTIFIED BY 'historian';

-- GRANT <access or ALL PRIVILEGES> ON <dbname>.<tablename or *> TO '<username>'@'host'
GRANT SELECT, INSERT, DELETE ON test_historian.* TO 'historian'@'localhost';

-- GRANT UPDATE ON <dbname>.<topics_table> TO 'username'@'localhost';
GRANT UPDATE ON test_historian.topics TO 'historian'@'localhost';

-- 
-- TO Run test_historian.py you need additional create and index privileges
-- 
GRANT CREATE, INDEX, DROP ON test_historian.* TO 'historian'@'localhost';

-- 
-- Run the below commands if you want to update your existing schema (separate topics and meta table) to have metadata
-- included in topics table
-- 
ALTER table topics ADD COLUMN metadata TEXT;
UPDATE topics t SET metadata = (SELECT metadata from meta where topic_id = t.topic_id);

-- 
-- If you are using aggregate historians with mysql create and grant access to additional tables
-- 
CREATE TABLE aggregate_topics
      (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT,
       agg_topic_name varchar(512) NOT NULL,
       agg_type varchar(20) NOT NULL,
       agg_time_period varchar(20) NOT NULL,
       PRIMARY KEY (agg_topic_id),
       UNIQUE(agg_topic_name, agg_type, agg_time_period));

CREATE TABLE aggregate_meta
    (agg_topic_id INTEGER NOT NULL,
     metadata TEXT NOT NULL,
     PRIMARY KEY(agg_topic_id));

-- FOR EACH CONFIGURED AGGREGATION execute the following where aggregate_data_table is aggregation_type+"_"+aggregation_period
-- for example avg_10m for 10 minute average

-- 
-- SCHEMA UPDATE FROM VERSION 4.0.0 Aggregate historian version 4.0.0 is NOT backward compatible with old schema 
-- 
-- As of aggregate historian version 4.0.0 the aggregate value is stored as double in the column agg_value (instead
-- saving as TEXT in column named value_string)

CREATE TABLE <aggregate_data_table>
      (ts timestamp(6) NOT NULL, topic_id INTEGER NOT NULL,
       agg_value DOUBLE NOT NULL, topics_list TEXT,
       UNIQUE(topic_id, ts),
       INDEX (ts ASC))

-- 
-- If upgrading aggregate tables from aggregate historian < version 4.0.0. You should manually update the table schema
-- 
ALTER TABLE aggregate_topics RENAME value_string TO agg_value;
ALTER TABLE aggregate_topics modify agg_value DOUBLE;
-- The above two update statements will fail if you have values in agg_value column that cannot be cast into double.
-- In that case you will not be able to update to the new schema without deleting those records.

ALTER TABLE aggregate_topics modify agg_type varchar(20);
ALTER TABLE aggregate_topics modify agg_time_period varchar(20);

-- NOTE: The above two update statements will fail if there are entries in the table that are greater than
-- 20 characters in length
-- You can find these records using the commands
SELECT agg_type FROM aggregate_topics WHERE length(agg_type)>20;
SELECT agg_time_period FROM aggregate_topics WHERE length(agg_time_period)>20;
-- If you want simply truncate the values to 20 character length you can update the records using the below statement
UPDATE aggregate_topics SET agg_type=substring(agg_type, 1, 20), agg_time_period=substring(agg_time_period, 1, 20);

-- GRANT UPDATE ON <dbname>.aggregate_topics TO 'username'@'localhost';
GRANT UPDATE ON test_historian.aggregate_topics TO 'historian'@'localhost';
GRANT UPDATE ON test_historian.aggregate_meta TO 'historian'@'localhost';

