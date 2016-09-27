
try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from bson.objectid import ObjectId
from pymongo import ReplaceOne

source_params = {
            "host": "vc-db1.pnl.gov",
            "port": 27017,
            "database": "prod_historian",
            "user": "reader",
            "passwd": ""
        }

dest_params = {
            "host": "vc-db1.pnl.gov",
            "port": 27017,
            "database": "historian_dev2",
            "user": "hdev",
            "passwd": "",
            "authSource": "admin"
        }

local_dest_params = {
            "host": "localhost",
            "port": 27017,
            "database": "performance_test",
            "user": "test",
            "passwd": "test",
            "authSource": "mongo_test"
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

def copy(source_params, dest_params, start_date, end_date):
    source_db = connect_mongodb(source_params)
    source_tables = get_table_names(source_params)

    dest_db = connect_mongodb(dest_params)
    dest_tables = get_table_names(dest_params)

    # records = []
    # for record in source_db[source_tables['topics_table']].find():
    #     records.append(record)
    # print("total records {}".format(len(records)))
    # dest_db[dest_tables['topics_table']].insert_many(
    #     records)
    #
    # records = []
    # for record in source_db[source_tables['meta_table']].find():
    #     records.append(record)
    # print("total records {}".format(len(records)))
    # dest_db[dest_tables['meta_table']].insert_many(
    #     records)

    # This is probably the most inefficient way of doing a copying a subset
    # of a
    # collection to another database but this is the one that requires the
    # minimum access
    # Wish this feature request is closed soon
    # https://jira.mongodb.org/browse/SERVER-13201
    # Aggregation is the fastest way to get a subset of data from a collection,
    # next would be map reduce. map reduce can write output to another db
    # but it would only generate doc of schema
    # id:<object id>, value:<search/mapreduce result>

    dest_db[dest_tables['data_table']].create_index(
        [('topic_id', pymongo.DESCENDING),
         ('ts', pymongo.DESCENDING)],
        unique=True, background=False)
    records = []
    i = 0
    print ("start obj:{}".format(ObjectId.from_datetime(start_date)))
    print ("end obj:{}".format(ObjectId.from_datetime(end_date)))
    cursor = source_db[source_tables['data_table']].find(
        {'$and':
            [{'_id': {'$gte': ObjectId.from_datetime(start_date)}},
             {'_id': {'$lte': ObjectId.from_datetime(end_date)}}]})
    print ("Record count from cursor {}".format(cursor.count()))
    for record in cursor:
        i += 1
        records.append(
                    ReplaceOne(
                        {'ts':record['ts'], 'topic_id':record['topic_id']},
                        {'ts': record['ts'], 'topic_id': record['topic_id'],
                                'value': record['value']},
                        upsert=True))
        if i == 2000:
            print("total records {}".format(len(records)))
            dest_db[dest_tables['data_table']].bulk_write(records)
            i =0
            records = []



    # cursor = dest_db[dest_tables['data_table']].aggregate([
    #     {"$group": {
    #         "_id": {"ts": "$ts", "topic_id": "$topic_id"},
    #         "duplicates": {"$push": "$_id"},
    #         "count": {"$sum": 1}
    #     }},
    #     {"$match": {"count": {"$gt": 1}}}
    # ])
    # for doc in cursor:
    #     doc.dups.shift()
    #     dest_db[dest_tables['data_table']].remove(
            # {"_id": {"$in":  doc.duplicates}})


if __name__ == '__main__':

    copy(source_params, local_dest_params, datetime.strptime('31Mar2016',
                                                         '%d%b%Y'),
         datetime.strptime('01May2016', '%d%b%Y'))


