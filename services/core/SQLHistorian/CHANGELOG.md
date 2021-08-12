**4.0.0**

    1. **DB schema change** to merge metadata details into topic table instead of separate metadata table. 
       The historian will create tables using this new schema for any new database configuration provided (if historian 
       has permissions to create tables). If historian detects existing tables it will not update to new schema and 
       continue to work with separate metadata table and topics tables.
    2. Historian's with utility class extending from volttron.platform.dbutils.DBDriver(from 
       volttron.platform.dbutils.basedb.py) and using the new schema, should implement three additional methods- 
       insert_topic_and_meta_query(), update_topic_and_meta_query(), and  'update_meta_query() 
    3. Bulk inserts metadata if metadata is in a separate table.
    4. Caches metadata at startup for performance improvement 
