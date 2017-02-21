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

local_source_params = {"host": "localhost",
                       "port": 27017,
                       "database": "historian",
                       "user": "historian",
                       "passwd": "volttron"}

local_dest_params = {"host": "localhost",
                     "port": 27017,
                     "database": "historian",
                     "user": "historian",
                     "passwd": "volttron"}

DAILY_COLLECTION = "daily_data"
HOURLY_COLLECTION = "hourly_data"
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

            # Perform insert if we have 3000 rows
            d_errors = h_errors = False
            if h == 10000:
                #print("In loop. bulk write hour")
                h_errors = execute_batch(bulk_hourly)
                if not h_errors:
                    bulk_hourly = dest_db[
                        HOURLY_COLLECTION].initialize_ordered_bulk_op()
                    h = 0

            if d == 10000:
                #print("In loop. bulk write day")
                d_errors = execute_batch(bulk_daily)
                if not d_errors:
                    bulk_daily = dest_db[
                        DAILY_COLLECTION].initialize_ordered_bulk_op()
                    d = 0

            if d_errors or h_errors:
                # something failed in bulk write. try from last err
                # row during the next periodic call
                print("error writing into daily: {} error writing into "
                      "hourly: {}".format(d_errors, h_errors))
                return

        # Perform insert for any pending records
        if h > 0:
            execute_batch(bulk_hourly)
        if d > 0:
            execute_batch(bulk_daily)

    finally:
        if cursor:
            cursor.close()
        if source_db:
            source_db.client.close()
        if dest_db:
            dest_db.client.close()
        #print ("Total time for roll up of data in topics {}: {}".format(
        #    topic_name, datetime.utcnow() - start))


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
            {"$multiply": ["$m", 60, 1000]}]}]}, 'topic_id': 1,
        'sum': {"$literal": 0}, 'count': {"$literal": 0},
        'data': {"$literal": [[]] * 60}}})

    pipeline.append({"$out": HOURLY_COLLECTION})
    db[data_collection].aggregate(pipeline, allowDiskUse=True)


if __name__ == '__main__':
    start = datetime.utcnow()
    start_date = '01Jan1980T00:00:00.000'
    end_date = '02Dec2016T00:00:00.000'
    print ("Starting rollup of data from {} to {}. current time: {}".format(
        start_date, end_date, start))

    pool = Pool(size=10)
    try:
        source_db = connect_mongodb(local_source_params)
        source_tables = get_table_names(local_source_params)
        print ("Starting init of tables")
        source_db = connect_mongodb(local_source_params)
        s_dt = datetime.strptime(start_date, '%d%b%YT%H:%M:%S.%f')
        e_dt = datetime.strptime(end_date, '%d%b%YT%H:%M:%S.%f')
        init_start = datetime.utcnow()
        init_daily_data(source_db, source_tables['data_table'], s_dt, e_dt)
        print ("Total time for init of daily data between {} and {} : {} "
               "".format(start_date, end_date, datetime.utcnow() - init_start))
        init_start = datetime.utcnow()
        init_hourly_data(source_db, source_tables['data_table'], s_dt, e_dt)
        print ("Total time for init of hourly data between {} and {} : {} "
               "".format(start_date, end_date, datetime.utcnow() - init_start))

        cursor = source_db[source_tables['topics_table']].find({}).sort(
            "_id", pymongo.ASCENDING)

        topics = list(cursor)
        max = len(topics)

        for i in xrange(0, max):
            print("Processing topic: {} {}".format(topics[i]['_id'],
                                                   topics[i]['topic_name']))
            pool.spawn(rollup_data, local_source_params,
                       local_dest_params,
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



