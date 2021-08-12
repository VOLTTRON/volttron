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
    5. historian no longer records table names in a metadata table(volttron_table_definitions). This was done primarily
       for the use of aggregate historian. Now aggregate historian config support table names and will not try to read 
       it from metadata table
    6. Support for newer version of MySQL - Mysql 8
    7. Mysql and postgres historian now do bulk update for data and topics table
    
        
