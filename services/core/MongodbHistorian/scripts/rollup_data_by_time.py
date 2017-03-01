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

def hourly_rollup(source_params, dest_params, start_date, end_date):

    source_db = None
    dest_db = None
    try:
        source_db = connect_mongodb(source_params)
        source_tables = get_table_names(source_params)

        dest_db = connect_mongodb(dest_params)
        dest_tables = get_table_names(dest_params)

        dest_db['hourly_data'].create_index(
            [('topic_id', pymongo.DESCENDING),
             ('ts', pymongo.DESCENDING)],
            unique=True, background=False)

        # temporary index so that initial rollup into daily and monthly
        # happens faster
        dest_db['hourly_data'].create_index(
            [('ts', pymongo.ASCENDING)],
            background=False)

        cursor = source_db[source_tables['data_table']].find(
            {'ts': {'$gte': start_date,'$lt': end_date}}
        ).sort([('topic_id', pymongo.ASCENDING), ('ts', pymongo.ASCENDING)])



        print ("Record count from cursor {}".format(cursor.count()))
        topic_id =''
        date = ''
        hour =''
        sum = 0
        count = 0
        data = []
        for record in cursor:

            if topic_id != record['topic_id'] or \
                date != record['ts'].date() or \
                hour != record['ts'].hour:
                #Found next record

                if topic_id:

                    # if this is not the first iteration, update  data array
                    # of previous (topic_id, date, hour)
                    # reset sum, count and data array
                    print ("update for {}, {}".format(
                        topic_id,
                        datetime(date.year, date.month, date.day, hour)))

                    dest_db['hourly_data'].update_one(
                        {'topic_id': topic_id, 'ts':
                            datetime(date.year, date.month, date.day, hour)},
                        {"$set":{'sum':sum, 'count':count, 'data':data}}
                    )
                    sum = 0
                    count = 0
                    data = []

                #reset variables
                topic_id = record['topic_id']
                date = record['ts'].date()
                hour = record['ts'].hour

                # insert new record for current topic, date and hour
                dest_db['hourly_data'].replace_one(
                    {'topic_id': topic_id,
                     'ts': datetime(date.year, date.month, date.day, hour)
                     },
                    {'topic_id': topic_id,
                     'ts': datetime(date.year, date.month, date.day, hour)
                    }, upsert=True)
                # print("Finished insert for {} , {}".format(
                #     topic_id,
                #     datetime(date.year, date.month, date.day, hour)
                # ))

            # append data and calculate aggregate values
            data.append((record['ts'], record['value']))
            if isinstance(record['value'], Number):
                sum = sum + record['value']
                count = count + 1
    finally:
        if source_db:
            source_db.client.close()
        if dest_db:
            dest_db.client.close()


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
            {"$match": {'ts': {"$gte": start_date, "$lt": end_date}}})
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
        pipeline.append({"$out":"daily_data"})

        dest_db['hourly_data'].aggregate(pipeline, allowDiskUse=True)

    finally:
        if dest_db:
            dest_db.client.close()

def monthly_rollup(db_params, start_date, end_date):

    dest_db = None
    try:
        dest_db = connect_mongodb(db_params)

        dest_db['monthly_data2'].create_index(
            [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
            unique=True, background=False)


        pipeline = []
        pipeline.append({"$match":{'ts': {"$gte":start_date, "$lt":end_date}}})
        pipeline.append({'$group' : {
                       '_id' : {'topic_id':"$topic_id",
                                'year':{"$year":"$ts"},
                                'month':{"$month":"$ts"}},
                       'year':{"$first":{"$year":"$ts"}},
                       'month':{"$first":{"$month":"$ts"}},
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
                                        {"$multiply" : [ "$h",  60,  60,
                                                         1000]},
                                        {"$multiply": [{"$subtract":[
                                            "$dayOfMonth", 1]},
                                            24, 60, 60, 1000]}
                                        ]}
                                   ]},
            'topic_id':1,
            'sum': 1,
            'count': 1,
            'data': 1}})
        pipeline.append({"$out":"monthly_data"})
        print (pipeline)
        dest_db['daily_data'].aggregate(pipeline, allowDiskUse=True)

    finally:
        if dest_db:
            dest_db.client.close()

def rollup_data(source, dest, start, end):
    hourly_rollup(source, dest, start, end)
    daily_rollup(local_dest_params, start, end)
    monthly_rollup(dest, start, end)

if __name__ == '__main__':
    start = datetime.utcnow()
    rollup_data(local_source_params, local_dest_params,
         datetime.strptime('01May2016','%d%b%Y'),
         datetime.strptime('16May2016','%d%b%Y'))
    print ("Total time for roll up of data: {}".format(datetime.utcnow() -
                                                       start))

