**4.0.0**

    1. **DB schema change** - Saves aggregations as double precision instead of text. Support for string aggregations 
       such as group_concat is removed
       aggregates are stored in column agg_value of type DOUBLE instead of string_value of type TEXT
    2. ** DB schema change** - aggregate topics are stored in table with modified schema
        aggregate_topics
          (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT,
           agg_topic_name varchar(512) NOT NULL,
           **agg_type varchar(20)**NOT NULL,   -- changed from varchar(512) to varchar(20)
           **agg_time_period varchar(20)** NOT NULL, - changed from varchar(512) to varchar(20)
           PRIMARY KEY (agg_topic_id),
           UNIQUE(agg_topic_name, agg_type, agg_time_period)); - reduced above lengths so that index is not too long
    3. Fixes bug in aggregate historian where there is more than one instance pointing to same db. Configuration of 
       aggregate historian now support definition table names. This way more than one aggregate historian and historian
       can use the same database with different table names
