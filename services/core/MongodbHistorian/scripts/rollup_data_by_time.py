import re

from gevent import monkey
monkey.patch_all()

try:
    import pymongo
except:
    raise Exception("Required: pymongo")
from datetime import datetime
from numbers import Number
from pymongo.errors import BulkWriteError
from gevent.pool import Pool


### START - Variables to set before running script ##
local_source_params = {"host": "localhost",
                       "port": 27017,
                       "authSource":"mongo_test",
                       "database": "performance_test",
                       "user": "test",
                       "passwd": "test"}

DAILY_COLLECTION = "daily_data"
HOURLY_COLLECTION = "hourly_data"
log_out_file = "./script_out"
init_rollup_tables = True # Set this to false if init is already done and if
#  you are rerunning to script for different date range or topic pattern
start_date = '30Mar2016T00:00:00.000'
end_date = '10Feb2017T00:00:00.000'
topic_patterns = ["^Economizer_RCx|^Airside_RCx",
                  '^PNNL-SEQUIM', '^pnnl',
                  '^datalogger', '^record']
### END - Variables to set before running script ##

import sys
log = open(log_out_file, 'w', buffering=1)
sys.stdout = log
sys.stderr = log
#log = None


def connect_mongodb(connection_params):

    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    if connection_params.get('authSource'):
        mongo_conn_str = mongo_conn_str + '?authSource={authSource}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)

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
    cursor = None
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
            match_condition, no_cursor_timeout=True).sort(
            "_id", pymongo.ASCENDING)

        # Iterate and append to a bulk_array. Insert in batches of 3000
        d = 0
        h = 0
        bulk_hourly = dest_db[HOURLY_COLLECTION].initialize_ordered_bulk_op()
        bulk_daily = dest_db[DAILY_COLLECTION].initialize_ordered_bulk_op()
        last_init_hour = None
        last_init_day = None
        for row in cursor:
            if not stat or row['_id'] > stat["last_data_into_hourly"]:
                # ts_hour = row['ts'].replace(minute=0, second=0,
                #                             microsecond=0)
                # if last_init_hour is None or ts_hour != last_init_hour :
                #     # above check would work since we use 1 thread per topic
                #     initialize_hourly(topic_id=row['topic_id'],
                #                       ts_hour=ts_hour,
                #                       db=dest_db)
                #     last_init_hour = ts_hour
                insert_to_hourly(bulk_hourly, row['_id'],
                    topic_id=row['topic_id'], ts=row['ts'], value=row['value'])
                h += 1
                #print("Insert bulk op to hourly. h= {}".format(h))

            if not stat or row['_id'] > stat["last_data_into_daily"]:
                # ts_day = row['ts'].replace(hour=0, minute=0,
                #                            second=0, microsecond=0)
                # if last_init_day is None or ts_day != last_init_day:
                #     initialize_daily(topic_id=row['topic_id'], ts_day=ts_day,
                #                       db=dest_db)
                #     last_init_day = ts_day
                insert_to_daily(bulk_daily, row['_id'],
                                topic_id=row['topic_id'], ts=row['ts'],
                                value=row['value'])
                d += 1
                #print("Insert bulk op to daily  d= {}".format(d))

            # Perform insert if we have 10000 rows
            d_errors = h_errors = False
            if h == 10000:
                #print("In loop. bulk write hour")
                h_errors = execute_batch("hourly", bulk_hourly, h, topic_id,
                                         topic_name)
                if not h_errors:
                    bulk_hourly = dest_db[
                        HOURLY_COLLECTION].initialize_ordered_bulk_op()
                    h = 0

            if d == 10000:
                #print("In loop. bulk write day")
                d_errors = execute_batch("daily", bulk_daily, d, topic_id,
                                         topic_name)
                if not d_errors:
                    bulk_daily = dest_db[
                        DAILY_COLLECTION].initialize_ordered_bulk_op()
                    d = 0

            if d_errors or h_errors:
                # something failed in bulk write. try from last err
                # row during the next periodic call
                print(
                    "error writing into {} data collection for topic: "
                    "{}:{}".format("hourly" if h_errors else "daily",
                                   topic_id, topic_name))
                return

        # Perform insert for any pending records
        if h > 0:
            h_errors = execute_batch("hourly", bulk_hourly, h, topic_id,
                                     topic_name)
            if h_errors:
                print("Error processing data into daily collection. "
                      "topic {}:{}".format(topic_id, topic_name))
        if d > 0:
            d_errors = execute_batch("daily", bulk_daily, d, topic_id,
                                     topic_name)
            if d_errors:
                print("Error processing data into daily collection. "
                      "topic {}:{}".format(topic_id, topic_name))
    except Exception as e:
        print("Exception processing topic {}:{} {}".format(topic_id,
                                                           topic_name,
                                                           e.args))
    finally:
        if cursor:
            cursor.close()
        if source_db:
            source_db.client.close()
        if dest_db:
            dest_db.client.close()


def get_last_back_filled_data(db, collection, topic_id, topic_name):
    id = ""
    match_condition = {'topic_id': topic_id}
    cursor = db[collection].find(match_condition).sort("last_back_filled_data",
        pymongo.DESCENDING).limit(1)
    for row in cursor:
        id = row.get('last_back_filled_data')

    return id


def execute_batch(table_type, bulk, count, topic_id, topic_name):
    """
    Execute bulk operation. return true if operation completed successfully
    False otherwise
    """
    errors = False
    try:
        result = bulk.execute()
        if result['nModified'] != count:
            print(
                "bulk execute of {} data for {}:{}.\nnumber of op sent to "
                "bulk execute ({}) does not match nModified count".format(
                    table_type, topic_id, topic_name, count))
            print ("bulk execute result {}".format(result))
            errors = True
    except BulkWriteError as ex:
        print(str(ex.details))
        errors = True

    return errors


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


def init_daily_data(db, data_collection, start_dt, end_dt):
    pipeline = []
    if start_date and end_date:
        pipeline.append({"$match":
                             {'ts': {"$gte": start_dt, "$lt": end_dt}}})
    pipeline.append({'$group': {
        '_id': {'topic_id': "$topic_id", 'year': {"$year": "$ts"},
                'month': {"$month": "$ts"},
                'dayOfMonth': {"$dayOfMonth": "$ts"}},
        'h': {"$first": {"$hour": "$ts"}},
        'm': {"$first": {"$minute": "$ts"}},
        's': {"$first": {"$second": "$ts"}},
        'ml': {"$first": {"$millisecond": "$ts"}}, 'ts': {"$first": "$ts"},
        'topic_id': {"$first": "$topic_id"}, 'sum': {"$sum": "$sum"},
        'count': {"$sum": "$count"}}})
    pipeline.append({'$project': {'_id': 0, 'ts': {"$subtract": ["$ts", {
        "$add": ["$ml", {"$multiply": ["$s", 1000]},
                 {"$multiply": ["$m", 60, 1000]},
                 {"$multiply": ["$h", 60, 60, 1000]}]}]}, 'topic_id': 1,
        'sum': {"$literal": 0}, 'count': {"$literal": 0},
        'data': {"$literal": [[]] * 24 * 60}}})

    pipeline.append({"$out": DAILY_COLLECTION})
    db[data_collection].aggregate(pipeline, allowDiskUse=True)


def init_hourly_data(db, data_collection, start_dt, end_dt):

    pipeline = []
    pipeline.append({"$match": {'ts': {"$gte": start_dt, "$lt": end_dt}}})
    pipeline.append({'$group': {
        '_id': {'topic_id': "$topic_id",
                'year': {"$year": "$ts"},
                'month': {"$month": "$ts"},
                'dayOfMonth': {"$dayOfMonth": "$ts"},
                'hour': {"$hour": "$ts"}},
        'm': {"$first": {"$minute": "$ts"}},
        's': {"$first": {"$second": "$ts"}},
        'ml': {"$first": {"$millisecond": "$ts"}},
        'ts': {"$first": "$ts"},
        'topic_id': {"$first": "$topic_id"},
        'sum': {"$sum": "$sum"},
        'count': {"$sum": "$count"}}})
    pipeline.append({'$project': {
        '_id': 0,
        'ts': {"$subtract": [
                    "$ts", {
                    "$add": [
                        "$ml",
                        {"$multiply": ["$s", 1000]},
                        {"$multiply": ["$m", 60, 1000]}]
                    }]},
        'topic_id': 1,
        'sum': {"$literal": 0}, 'count': {"$literal": 0},
        'data': {"$literal": [[]] * 60}}})

    pipeline.append({"$out": HOURLY_COLLECTION})
    db[data_collection].aggregate(pipeline, allowDiskUse=True)


if __name__ == '__main__':
    start = datetime.utcnow()

    print ("Starting rollup of data from {} to {}. current time: {}".format(
        start_date, end_date, start))

    pool = Pool(size=10)
    try:
        source_db = connect_mongodb(local_source_params)
        source_tables = get_table_names(local_source_params)
        init_done = False
        if init_rollup_tables:
            existing_collections = source_db.collection_names()
            if HOURLY_COLLECTION in existing_collections:
                print(
                    "init_rollup_tables set to True and hourly collection "
                    "name is set as {}. But this collection already exists "
                    "in the database. Exiting to avoid init process "
                    "overwriting existing collection {}. Please rename "
                    "collection in db or change value of "
                    "HOURLY_COLLECTION in script".format(
                        HOURLY_COLLECTION, HOURLY_COLLECTION))
            elif DAILY_COLLECTION in existing_collections:
                print(
                    "init_rollup_tables set to True and daily collection "
                    "name is set as {}. But this collection already exists "
                    "in the database. Exiting to avoid init process "
                    "overwriting existing collection {}. Please rename "
                    "collection in db or change value of "
                    "DAILY_COLLECTION in script".format(
                        DAILY_COLLECTION, DAILY_COLLECTION))
            else:
                source_db = connect_mongodb(local_source_params)
                s_dt = datetime.strptime(start_date, '%d%b%YT%H:%M:%S.%f')
                e_dt = datetime.strptime(end_date, '%d%b%YT%H:%M:%S.%f')
                print ("Starting init of tables")
                init_start = datetime.utcnow()
                init_daily_data(source_db,
                                source_tables['data_table'],
                                s_dt,
                                e_dt)
                print ("Total time for init of daily data "
                       "between {} and {} : {} "
                       "".format(start_date, end_date,
                                 datetime.utcnow() - init_start))
                init_start = datetime.utcnow()
                init_hourly_data(source_db,
                                 source_tables['data_table'],
                                 s_dt,
                                 e_dt)
                print ("Total time for init of hourly data "
                       "between {} and {} : {} "
                       "".format(start_date, end_date,
                                 datetime.utcnow() - init_start))
                init_done = True
        else:
            init_done = True

        if init_done:
            for topic_pattern in topic_patterns:
                regex = re.compile(topic_pattern, re.IGNORECASE)
                cursor = source_db[source_tables['topics_table']].find(
                    {"topic_name": regex}).sort("_id", pymongo.ASCENDING)

                topics = list(cursor)
                max = len(topics)
                print("Total number of topics with the pattern{}: {}".format(
                    topic_pattern, max))

                for i in range(0, max):
                    print("Processing topic: {} {}".format(topics[i]['_id'],
                                                           topics[i]['topic_name']))
                    pool.spawn(rollup_data, local_source_params,
                               local_source_params,
                               datetime.strptime(start_date, '%d%b%YT%H:%M:%S.%f'),
                               datetime.strptime(end_date, '%d%b%YT%H:%M:%S.%f'),
                               topics[i]['_id'], topics[i]['topic_name'])

                pool.join()

    except Exception as e:
        print("Exception processing data: {}".format(e.args))
    finally:
        pool.kill()
        print ("Total time for roll up of data : {}".format(
            datetime.utcnow() - start))
        if log:
            log.close()



