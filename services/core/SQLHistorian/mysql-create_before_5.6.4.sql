-- This script assumes that the user has access to create the database.
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
