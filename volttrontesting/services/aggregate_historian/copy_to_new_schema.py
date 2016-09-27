import pytz

try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from bson.objectid import ObjectId
from pymongo import ReplaceOne
from numbers import Number

from volttron.platform.agent import utils


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

def copy(source_params, dest_params, start_date, end_date):
    source_db = connect_mongodb(source_params)
    source_tables = get_table_names(source_params)

    dest_db = connect_mongodb(dest_params)
    dest_tables = get_table_names(dest_params)

    records = []
    for record in source_db[source_tables['topics_table']].find():
        records.append(record)
    print("total records {}".format(len(records)))
    dest_db[dest_tables['topics_table']].insert_many(
        records)

    records = []
    for record in source_db[source_tables['meta_table']].find():
        records.append(record)
    print("total records {}".format(len(records)))
    dest_db[dest_tables['meta_table']].insert_many(
        records)

    dest_db['hourly_data'].create_index(
        [('topic_id', pymongo.DESCENDING),
         ('date_hr', pymongo.DESCENDING)],
        unique=True, background=False)


    print ("start obj:{}".format(ObjectId.from_datetime(start_date)))
    print ("end obj:{}".format(ObjectId.from_datetime(end_date)))

    # cursor = source_db[source_tables['data_table']].find(
    #     {'$and':
    #          [{'topic_id': {'$in': [ObjectId("569975abc56e520238fcdf86"),
    #                                 ObjectId("569975abc56e520238fcdf88")]}},
    #           {'ts': {'$gte': start_date}},
    #           {'ts': {'$lt': end_date}}]}
    # ).sort([('topic_id', pymongo.ASCENDING), ('ts', pymongo.ASCENDING)])

    cursor = source_db[source_tables['data_table']].find().\
        sort([('topic_id', pymongo.ASCENDING), ('ts', pymongo.DESCENDING)])

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
                    {'topic_id': topic_id, 'date_hr':
                        datetime(date.year, date.month, date.day, hour)},
                    {"$set":{'sum':sum, 'avg': sum/count if count>0 else 0 ,
                     'count':count,
                             'data':data}}
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
                 'date_hr': datetime(date.year, date.month, date.day, hour)
                 },
                {'topic_id': topic_id,
                 'date_hr': datetime(date.year, date.month, date.day, hour)
                }, upsert=True)
            print("Finished insert for {} , {}".format(
                topic_id,
                datetime(date.year, date.month, date.day, hour)
            ))

        # append data and calculate aggregate values
        data.append((record['ts'], record['value']))
        if isinstance(record['value'], Number):
            sum = sum + record['value']
            count = count + 1


if __name__ == '__main__':

    copy(local_source_params, local_dest_params,
         datetime.strptime('01Mar2016','%d%b%Y'),
         datetime.strptime('03Mar2016','%d%b%Y'))


