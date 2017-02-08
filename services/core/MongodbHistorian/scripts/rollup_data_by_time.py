try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from numbers import Number

from bson.objectid import ObjectId
from pymongo.errors import BulkWriteError
from pymongo.operations import UpdateOne
from dateutil.tz import tzutc
from gevent import monkey
monkey.patch_all()
import gevent
from gevent.threadpool import ThreadPool

local_source_params = {"host": "localhost",
                       "port": 27017,
                       "authSource": "mongo_test",
                       "database": "performance_test",
                       "user": "test",
                       "passwd": "test"}

local_dest_params = {"host": "localhost",
                     "port": 27017,
                     "authSource": "mongo_test",
                     "database": "performance_test",
                     "user": "test",
                     "passwd": "test"}

DAILY_COLLECTION = "daily_data2"
HOURLY_COLLECTION = "hourly_data2"
running_historian = True
import sys
log = open('./script_out', 'w', buffering=1)
sys.stdout = log
sys.stderr = log

def connect_mongodb(connection_params):
    #print ("setup mongodb")
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    if connection_params.get('authSource'):
        mongo_conn_str = mongo_conn_str + '?authSource={authSource}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)
    #print (mongo_conn_str)
    mongo_client = pymongo.MongoClient(mongo_conn_str)
    db = mongo_client[connection_params['database']]
    return db


def get_table_names(config):
    default_table_def = {"table_prefix": "", "data_table": "data",
                         "topics_table": "topics", "meta_table": "meta"}
    tables_def = config.get('tables_def', None)
    if not tables_def:
        tables_def = default_table_def
    table_names = dict(tables_def)
    table_names["agg_topics_table"] = "aggregate_" + tables_def["topics_table"]
    table_names["agg_meta_table"] = "aggregate_" + tables_def["meta_table"]

    table_prefix = tables_def.get('table_prefix', None)
    table_prefix = table_prefix + "_" if table_prefix else ""
    if table_prefix:
        for key, value in table_names.items():
            table_names[key] = table_prefix + table_names[key]

    return table_names


def rollup_data(source_params, dest_params, start_date, end_date, topic_id,
                topic_name):
    source_db = None
    dest_db = None
    start = datetime.utcnow()
    #match_count = 0
    try:

        source_db = connect_mongodb(source_params)
        source_tables = get_table_names(source_params)

        dest_db = connect_mongodb(dest_params)
        dest_tables = get_table_names(dest_params)

        dest_db[HOURLY_COLLECTION].create_index(
            [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
            unique=True, background=False)
        dest_db[HOURLY_COLLECTION].create_index(
            [('last_back_filled_data', pymongo.ASCENDING)], background=False)

        dest_db[DAILY_COLLECTION].create_index(
            [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
            unique=True, background=False)
        dest_db[DAILY_COLLECTION].create_index(
            [('last_back_filled_data', pymongo.ASCENDING)], background=False)

        match_condition = {'ts': {'$gte': start_date, '$lt': end_date}}
        match_condition['topic_id'] = topic_id

        stat = {}
        stat["last_data_into_daily"] = get_last_back_filled_data(
            dest_db, DAILY_COLLECTION, topic_id, topic_name)

        stat["last_data_into_hourly"] = get_last_back_filled_data(
            dest_db, HOURLY_COLLECTION, topic_id, topic_name)

        if stat["last_data_into_daily"]:
            match_condition['_id'] = {'$gt': stat["last_data_into_daily"]}
        if stat["last_data_into_hourly"]:
            if stat["last_data_into_daily"] and stat[
                "last_data_into_hourly"] < \
                    stat["last_data_into_daily"]:
                match_condition['_id'] = {'$gt': stat["last_data_into_hourly"]}
        if not stat["last_data_into_hourly"] and not stat[
            "last_data_into_daily"]:
            stat = {}

        cursor = source_db[source_tables['data_table']].find(
            match_condition).sort("_id", pymongo.ASCENDING)

        #print ("match condition: {}".format(match_condition))
        #print("Before looping through results for {}".format(topic_id))
        #imatch_count = cursor.count()
        # print (
        # "Record count for topic {} {} is {}".format(topic_id, topic_name,
        #     match_count))

        # Iterate and append to a bulk_array. Insert in batches of 3000
        d = 0
        h = 0
        bulk_hourly = dest_db[HOURLY_COLLECTION].initialize_ordered_bulk_op()
        bulk_daily = dest_db[DAILY_COLLECTION].initialize_ordered_bulk_op()
        bulk_init_hourly = dest_db[
            HOURLY_COLLECTION].initialize_ordered_bulk_op()
        bulk_init_daily = dest_db[
            DAILY_COLLECTION].initialize_ordered_bulk_op()
        hourly_needs_init = False
        daily_needs_init = False
        for row in cursor:
            if not stat or row['_id'] > stat["last_data_into_hourly"]:
                result = initialize_hourly(
                    bulk_init_hourly,
                    topic_id=row['topic_id'],
                    ts=row['ts'],
                    db=dest_db)
                if result:
                    hourly_needs_init = True
                insert_to_hourly(bulk_hourly, row['_id'],
                    topic_id=row['topic_id'], ts=row['ts'], value=row['value'])
                h += 1
                #print("Insert bulk op to hourly. h= {}".format(h))

            if not stat or row['_id'] > stat["last_data_into_daily"]:
                result = initialize_daily(
                    bulk_init_daily,
                    topic_id=row['topic_id'],
                    ts=row['ts'],
                    db=dest_db)
                if result:
                    daily_needs_init = True
                insert_to_daily(bulk_daily, row['_id'],
                                topic_id=row['topic_id'], ts=row['ts'],
                                value=row['value'])
                d += 1
                #print("Insert bulk op to daily  d= {}".format(d))

            # Perform insert if we have 3000 rows
            d_errors = h_errors = False
            if h == 5000:
                #print("In loop. bulk write hour")
                if hourly_needs_init:
                    h_errors = execute_batch(bulk_init_hourly)
                #print ("After bulk init hourly")
                if not h_errors:
                    h_errors = execute_batch(bulk_hourly)
                if not h_errors:
                    bulk_init_hourly = dest_db[
                        HOURLY_COLLECTION].initialize_ordered_bulk_op()
                    bulk_hourly = dest_db[
                        HOURLY_COLLECTION].initialize_ordered_bulk_op()
                    h = 0
                    hourly_needs_init = False
            if d == 5000:
                #print("In loop. bulk write day")
                if daily_needs_init:
                    d_errors = execute_batch(bulk_init_daily)
                if not d_errors:
                    d_errors = execute_batch(bulk_daily)
                if not d_errors:
                    bulk_init_daily = dest_db[
                        DAILY_COLLECTION].initialize_ordered_bulk_op()
                    bulk_daily = dest_db[
                        DAILY_COLLECTION].initialize_ordered_bulk_op()
                    d = 0
                    daily_needs_init = False

            if d_errors or h_errors:
                # something failed in bulk write. try from last err
                # row during the next periodic call
                print("error writing into daily: {} error writing into "
                      "hourly: {}".format(d_errors, h_errors))
                return

        # Perform insert for any pending records
        if h > 0:
            h_errors = False
            if hourly_needs_init:
                h_errors = execute_batch(bulk_init_hourly)
            if not h_errors:
                execute_batch(bulk_hourly)
        if d > 0:
            d_errors = False
            if daily_needs_init:
                d_errors = execute_batch(bulk_init_daily)
            if not d_errors:
                execute_batch(bulk_daily)

    finally:
        if source_db:
            source_db.client.close()
        if dest_db:
            dest_db.client.close()
        #if match_count > 0:
        # print ("Total time for roll up of data in topics {}: {}".format(
        #     topic_name, datetime.utcnow() - start))


def get_last_back_filled_data(db, collection, topic_id, topic_name):
    id = ""
    match_condition = {'topic_id': topic_id}
    cursor = db[collection].find(match_condition).sort("last_back_filled_data",
        pymongo.DESCENDING).limit(1)
    for row in cursor:
        id = row.get('last_back_filled_data')
        #print ("last processed data for topic_pattern {} in {} is {}".format(
        #    topic_name, collection, id))
    return id


def execute_batch(bulk):
    """
    Execute bulk operation. return true if operation completed successfully
    False otherwise
    """

    errors = False
    try:
        result = bulk.execute()
        # print ("bulk execute result {}".format(result))
    except BulkWriteError as ex:
        print(str(ex.details))
        errors = True

    return errors


def initialize_hourly(bulk_init, topic_id, ts, db):
    print ("In int hourly of {}".format(topic_id))
    ts_hour = ts.replace(minute=0, second=0, microsecond=0)

    needs_initializing = not db[HOURLY_COLLECTION].find(
        {'ts': ts_hour, 'topic_id': topic_id}).count() > 0
    print ("after check needs init={}".format(needs_initializing))
    if needs_initializing:
        if running_historian:
            # use update since historian could have initialized for the
            # same topic and ts sometime between when we checked and when we
            # do an insert
            bulk_init.find(
                {'ts': ts_hour, 'topic_id': topic_id}).upsert().update(
                {"$setOnInsert": {'ts': ts_hour, 'topic_id': topic_id,
                                  'count': 0, 'sum': 0, 'data': [[]] * 60,
                                  'last_back_filled_data': ''}})
        else:
            # else do insert since that is faster than update
            bulk_init.insert({'ts': ts_hour, 'topic_id': topic_id, 'count': 0,
                              'sum': 0, 'data': [[]] * 60,
                              'last_back_filled_data': ''})
    return needs_initializing


def initialize_daily(bulk_init, topic_id, ts, db):
    ts_day = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db[DAILY_COLLECTION].find(
        {'ts': ts_day, 'topic_id': topic_id}).count()
    needs_initializing = not count > 0
    if needs_initializing:
        if running_historian:
            # use update since historian could have initialized for the
            # same topic and ts sometime between when we checked and when we
            # do an insert
            bulk_init.find(
                {'ts': ts_day, 'topic_id': topic_id}).upsert().update(
                {"$setOnInsert": {'ts': ts_day, 'topic_id': topic_id,
                                  'count': 0, 'sum': 0,
                                  'data': [[]] * 24 * 60,
                                  'last_back_filled_data': ''}})
        else:
            # else do insert since that is faster than update
            bulk_init.insert({'ts': ts_day, 'topic_id': topic_id,
                              'count': 0, 'sum': 0, 'data': [[]] * 24 * 60,
                              'last_back_filled_data': ''})

    return needs_initializing


def insert_to_hourly(bulk_hourly, data_id, topic_id, ts, value):
    rollup_hour = ts.replace(minute=0, second=0, microsecond=0)
    sum_value = value_to_sumable(value)
    bulk_hourly.find({'ts': rollup_hour, 'topic_id': topic_id}).update(
        {'$push': {"data." + str(ts.minute): [ts, value]},
            '$inc': {'count': 1, 'sum': sum_value},
            '$set': {'last_back_filled_data': data_id}})


def insert_to_daily(bulk_daily, data_id, topic_id, ts, value):
    rollup_day = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    position = ts.hour * 60 + ts.minute
    sum_value = value_to_sumable(value)

    bulk_daily.find({'ts': rollup_day, 'topic_id': topic_id}).update_one(
        {'$push': {"data." + str(position): [ts, value]},
            '$inc': {'count': 1, 'sum': sum_value},
            '$set': {'last_back_filled_data': data_id}})


def value_to_sumable(value):
    # Handle the case where value is not a number so we don't
    # increment the sum for that instance.
    if isinstance(value, Number) and not isinstance(value, bool):
        sum_value = value
    else:
        sum_value = 0
    return sum_value


if __name__ == '__main__':
    start = datetime.utcnow()
    start_date = '02May2016T00:00:00.000'
    end_date = '03May2016T00:00:00.000'
    print ("Starting rollup of data from {} to {}. current time: {}".format(
        start_date, end_date, start))
    try:
        source_db = connect_mongodb(local_source_params)
        source_tables = get_table_names(local_source_params)
        cursor = source_db[source_tables['topics_table']].find({}).sort(
            "_id", pymongo.ASCENDING)

        pool = ThreadPool(maxsize=5)
        running_historian = False
        topics = list(cursor)
        max = len(topics)
        for i in xrange(0, max):
            print ("Processing topic: {} {}".format(topics[i]['_id'],
                                                    topics[i]['topic_name']))
            pool.spawn(rollup_data, local_source_params, local_dest_params,
                datetime.strptime(start_date, '%d%b%YT%H:%M:%S.%f'),
                datetime.strptime(end_date, '%d%b%YT%H:%M:%S.%f'),
                topics[i]['_id'], topics[i]['topic_name'])

        pool.join()
    finally:
        print ("Total time for roll up of data : {}".format(
               datetime.utcnow() - start))
        if log:
          log.close()

