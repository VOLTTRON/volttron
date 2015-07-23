
CREATE TABLE data (ts timestamp NOT NULL,
                                 topic_id INTEGER NOT NULL, 
                                 value_string TEXT NOT NULL, 
                                 UNIQUE(ts, topic_id));
            
CREATE INDEX data_idx ON data (ts ASC);

CREATE TABLE topics (topic_id INTEGER PRIMARY KEY, 
                                 topic_name varchar(512) NOT NULL,
                                 UNIQUE(topic_name));
