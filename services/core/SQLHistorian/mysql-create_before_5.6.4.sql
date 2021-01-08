-- This script assumes that the user has access to create the database.
-- update database name, user name, and password before executing the below commands
-- table names used below are default names used by historian. If you would like to customize table names
-- customize using the configuration tables_def and change the names in the below commands

CREATE DATABASE test_historian;

USE test_historian;

CREATE TABLE data (ts timestamp NOT NULL,
                                 topic_id INTEGER NOT NULL,
                                 value_string TEXT NOT NULL,
                                 UNIQUE(ts, topic_id));

CREATE INDEX data_idx ON data (ts ASC);

CREATE TABLE topics (topic_id INTEGER NOT NULL AUTO_INCREMENT,
                     topic_name varchar(512) NOT NULL,
                     PRIMARY KEY (topic_id),
                     UNIQUE(topic_name));

CREATE TABLE meta(topic_id INTEGER NOT NULL,
                  metadata TEXT NOT NULL,
                  PRIMARY KEY(topic_id));

CREATE TABLE volttron_table_definitions(
    table_id varchar(512) PRIMARY KEY,
    table_name varchar(512) NOT NULL,
    table_prefix varchar(512));


#Use the below syntax for creating user and grant access to the historian database

#CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';
CREATE USER 'historian'@'localhost' IDENTIFIED BY 'historian';

# GRANT <access or ALL PRIVILEGES> ON <dbname>.<tablename or *> TO '<username>'@'host'
GRANT SELECT, INSERT, DELETE ON test_historian.* TO 'historian'@'localhost';

# GRANT UPDATE ON <dbname>.<topics_table> TO 'username'@'localhost';
GRANT UPDATE ON test_historian.topics TO 'historian'@'localhost';


# TO Run test_historian.py you need additional create and index privileges
GRANT CREATE, INDEX ON test_historian.* TO 'historian'@'localhost';

# If you are using aggregate historians with mysql create and grant access to additional tables

CREATE TABLE aggregate_topics
      (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT,
       agg_topic_name varchar(512) NOT NULL,
       agg_type varchar(512) NOT NULL,
       agg_time_period varchar(512) NOT NULL,
       PRIMARY KEY (agg_topic_id),
       UNIQUE(agg_topic_name, agg_type, agg_time_period));

CREATE TABLE aggregate_meta
    (agg_topic_id INTEGER NOT NULL,
     metadata TEXT NOT NULL,
     PRIMARY KEY(agg_topic_id));

# FOR EACH CONFIGURED AGGREGATION execute the following where aggregate_data_table is aggregation_type+"_"+aggregation_period
# for example avg_10m for 10 minute average

CREATE TABLE <aggregate_data_table>
      (ts timestamp NOT NULL, topic_id INTEGER NOT NULL,
       value_string TEXT NOT NULL, topics_list TEXT,
       UNIQUE(topic_id, ts),
       INDEX (ts ASC))

# GRANT UPDATE ON <dbname>.aggregate_topics TO 'username'@'localhost';
GRANT UPDATE ON test_historian.aggregate_topics TO 'historian'@'localhost';
GRANT UPDATE ON test_historian.aggregate_meta TO 'historian'@'localhost';
