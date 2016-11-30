try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from pymongo import UpdateOne
from pymongo.errors import  BulkWriteError
from calendar import monthrange

mongo_params = {
            "host": "localhost",
            "port": 27017,
            "database": "performance_test",
            "user": "test",
            "passwd": "test",
            "authSource":"mongo_test"
        }

def connect_mongodb(connection_params):
    print ("setup mongodb")
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    if connection_params.get('authSource'):
        mongo_conn_str = mongo_conn_str+ '?authSource={authSource}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)
    print (mongo_conn_str)
    mongo_client = pymongo.MongoClient(mongo_conn_str)
    db = mongo_client[connection_params['database']]
    return db

def get_table_names(config):
    default_table_def = {"table_prefix": "",
                         "data_table": "data",
                         "topics_table": "topics",
                         "meta_table": "meta"}
    tables_def = config.get('tables_def', None)
    if not tables_def:
        tables_def = default_table_def
    table_names = dict(tables_def)
    table_names["agg_topics_table"] = \
        "aggregate_" + tables_def["topics_table"]
    table_names["agg_meta_table"] = \
        "aggregate_" + tables_def["meta_table"]

    table_prefix = tables_def.get('table_prefix', None)
    table_prefix = table_prefix + "_" if table_prefix else ""
    if table_prefix:
        for key, value in table_names.items():
            table_names[key] = table_prefix + table_names[key]

    return table_names

if __name__ == '__main__':
    start = datetime.utcnow()
    mongo_db = connect_mongodb(mongo_params)
    mongo_tables = get_table_names(mongo_params)
    ts = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0,
                                   microsecond=0)
    weekday, num_days = monthrange(ts.year, ts.month)

    cursor = mongo_db[mongo_tables['topics_table']].find()
    rows = list(cursor)
    bulk_write = []
    i = 0
    for row in rows:
        i += 1
        bulk_write.append(UpdateOne({'ts':ts,
                                     'topic_id':row['_id']},
                                    {"$setOnInsert":{'ts':ts,
                                     'topic_id':row['_id'],
                                     'count':0,
                                     'sum':0,
                                     'data':[[]]*num_days*24*60}},
                                    upsert=True))
        if i == 2000:
            mongo_db['monthly_data2'].bulk_write(bulk_write, ordered=False)
            i = 0
            bulk_write = []
    if bulk_write:
        mongo_db['monthly_data2'].bulk_write(bulk_write, ordered=False)

    # bulk = mongo_db['monthly_data2'].initialize_unordered_bulk_op()
    # i=0
    # for row in rows:
    #     i += 1
    #     bulk.insert({'ts':ts,
    #                  'topic_id':row['_id'],
    #                  'count':0,
    #                  'sum':0,
    #                  'data':[[]]*num_days*24*60})
    #     if  i==2000:
    #         try:
    #             bulk.execute()
    #         except BulkWriteError as bwr:
    #             pass
    #         i=0
    #         bulk = mongo_db['monthly_data2'].initialize_unordered_bulk_op()
    #
    print datetime.utcnow() - start