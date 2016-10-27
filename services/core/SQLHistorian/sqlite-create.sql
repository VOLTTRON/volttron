
CREATE TABLE IF NOT EXISTS data (ts timestamp NOT NULL,
                                 topic_id INTEGER NOT NULL, 
                                 value_string TEXT NOT NULL, 
                                 UNIQUE(ts, topic_id));
            
CREATE INDEX IF NOT EXISTS data_idx ON data (ts ASC);

CREATE TABLE IF NOT EXISTS topics (topic_id INTEGER PRIMARY KEY, 
                                 topic_name TEXT NOT NULL,
                                 UNIQUE(topic_name));

CREATE TABLE IF NOT EXISTS meta
    (topic_id INTEGER PRIMARY KEY,
     metadata TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS volttron_table_definitions(
    table_id TEXT PRIMARY KEY,
    table_name TEXT NOT NULL,
    table_prefix TEXT);
