-- This script assumes that the user has access to create the database.
CREATE DATABASE test_historian;

USE test_historian;

CREATE TABLE data (ts timestamp(6) NOT NULL,
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

CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';

# GRANT <access or ALL PRIVILEGES> ON <dbname>.<tablename or *> TO 'username'@'host'
GRANT SELECT, CREATE, INDEX, INSERT ON test_historian.* TO 'user'@'localhost';
GRANT UPDATE ON test_historian.<topics_table> TO 'user'@'localhost';
GRANT UPDATE ON test_historian.topics TO 'user'@'localhost';

# If you are using aggregate historians with mysql also grant udpate access to aggregate_topics
GRANT UPDATE ON test_historian.aggregate_topics TO 'user'@'localhost';

# For running test cases additional provide DELETE permission on the test database to the test user
GRANT DELETE ON test_historian.* TO 'user'@'localhost';
