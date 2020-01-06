# Script used just for reference. This shows how you can group data in hourly
# table into daily or monthly using mongo's aggregate framework.
# This is faster than the logic used in rollup_data_by_time.py but doesn't
# allow any good way to recover from failure

try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from numbers import Number

from bson.objectid import ObjectId

local_source_params = {
            "host": "localhost",
            "port": 27017,
            "database": "performance_test",
            "user": "test",
            "passwd": "test",
            "authSource":"mongo_test"
        }

local_dest_params = {
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

def daily_rollup(db_params, start_date, end_date):

    dest_db = None
    try:
        dest_db = connect_mongodb(db_params)

        dest_db['daily_data2'].create_index(
            [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
            unique=True, background=False)

        # temporary index so that initial rollup into daily and monthly
        # happens faster
        dest_db['daily_data2'].create_index([('ts', pymongo.ASCENDING)],
            background=False)

        pipeline = []
        pipeline.append(
            {"$match": {
                'ts': {"$gte": start_date, "$lt": end_date}}})
        pipeline.append({"$sort":{'ts':1}})
        pipeline.append({'$group' : {
                       '_id' : {'topic_id':"$topic_id", 'year':{"$year":"$ts"},
                                'month':{"$month":"$ts"},
                                'dayOfMonth':{"$dayOfMonth":"$ts"}},
                       'year':{"$first":{"$year":"$ts"}},
                       'month':{"$first":{"$month":"$ts"}},
                       'dayOfMonth':{'$first':{"$dayOfMonth":"$ts"}},
                       'ts': {"$first":"$ts"},
                       'topic_id': {"$first":"$topic_id"},
                       'sum': { "$sum": "$sum" },
                       'count': { "$sum": "$count" },
                       'data': {"$push": "$data"}
                        }})
        pipeline.append({"$unwind":"$data"})
        pipeline.append({"$unwind": "$data"})
        pipeline.append({'$group' : {
                        '_id': "$_id",
                        'ts': {"$first":"$ts"},
                        'year': {"$first": "$year"},
                        'month': {"$first": "$month"},
                        'dayOfMonth': {"$first": "$dayOfMonth"},
                        'h': {"$first":{"$hour":"$ts"}},
                        'm': {"$first":{"$minute":"$ts"}},
                        's': {"$first":{"$second":"$ts"}},
                        'ml': {"$first":{"$millisecond":"$ts"}},
                        'topic_id': {"$first": "$topic_id"},
                        'sum': { "$first": "$sum" },
                        'count': { '$first': "$count" },
                        'data': {'$push': "$data"}
                        }})
        pipeline.append({'$project':{
            '_id': 0,
            'ts':{ "$subtract" : [ "$ts",
                                   {"$add" : [
                                       "$ml",
                                        {"$multiply" : [ "$s", 1000 ] },
                                        {"$multiply" : [ "$m", 60, 1000 ]},
                                        {"$multiply" : [ "$h",  60,  60, 1000]}
                                        ]}
                                   ]},
            'topic_id':1,
            'sum': 1,
            'count': 1,
            'data': 1}})
        pipeline.append({"$out":"daily_data2"})

        dest_db['hourly_data2'].aggregate(pipeline, allowDiskUse=True)

    finally:
        if dest_db:
            dest_db.client.close()


def rollup_data(source, dest, start, end):
     daily_rollup(local_dest_params, start, end)


if __name__ == '__main__':
    start = datetime.utcnow()
    rollup_data(local_source_params, local_dest_params,
         datetime.strptime('02May2016','%d%b%Y'),
         datetime.strptime('03May2016','%d%b%Y'))
    print("Total time for roll up of data: {}".format(datetime.utcnow() - start))

