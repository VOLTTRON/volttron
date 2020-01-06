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


#Use the below syntax for creating user and grant access to the historian database

CREATE USER 'username'@'localhost' IDENTIFIED BY 'password';

#GRANT <access or ALL PRIVILEGES> ON <dbname>.<tablename or *> TO 'username'@'host'
GRANT SELECT, CREATE, INDEX, INSERT ON test_historian.* TO 'user'@'localhost';
GRANT UPDATE ON test_historian.topics TO 'historian'@'localhost';

# For running test cases additional provide DELETE permission on the test database to the test user
GRANT DELETE ON test_historian.* TO 'user'@'localhost';