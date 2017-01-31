from datetime import timedelta
import hashlib
import logging
import os
import sys
from time import sleep
from threading import Thread
import Queue

from crate import client as crate_client
import pymongo
from zmq.utils import jsonapi

from volttron.platform.agent import utils
from volttron.platform.dbutils import cratedriver
from volttron.platform.dbutils import mongoutils

logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger(__name__)

for key in logging.Logger.manager.loggerDict:
    print(key)

logging.getLogger('crate.client.http').setLevel(logging.INFO)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

root = os.path.dirname(os.path.abspath(__file__))
with open('{}/crate_config'.format(root), 'r') as fp:
    data = jsonapi.loads(fp.read())

crate_params = data['connection']['params']['host']

root = os.path.dirname(os.path.abspath(__file__))
with open('{}/mongo_config'.format(root), 'r') as fp:
    data = jsonapi.loads(fp.read())

mongo_params = data['connection']['params']['host']

class TableQueue(Queue.Queue, object):
    def __init__(self, table_name):
        super(TableQueue, self).__init__()
        self.table_name = table_name


def get_mongo_db():
    mongo_client = mongoutils.get_mongo_client(mongo_params["connection"]["params"])

    return mongo_client.get_default_database()

insert_errors = open('insert_error.log', mode='w')
topics = {}
table_names = ('device', 'analysis', 'record', 'datalogger')

# Create a queue for each of the tables.
table_queues = {}
for t in table_names:
    table_queues[t] = TableQueue(t)

total_time = 0
batch = []
batch_table_name = {}
for t in table_names:
    batch_table_name[t] = []


def build_topics_mapping():
    global topics
    mongo_db = get_mongo_db()

    for obj in mongo_db.topics.find({}):
        tname = obj['topic_name']
        tsplit = tname.split('/')
        hash = hashlib.md5(tname).hexdigest()
        topics[obj['_id']] = dict(name=tname, hash=hash)
        if tsplit[0] in ('PNNL', 'PNNL-SEQUIM', 'pnnl', 'pnnl-SEQUIM'):
            topics[obj['_id']]['table'] = 'device'
        elif tsplit[0] in ('Economizer_RCx', 'Airside_RCx'):
            topics[obj['_id']]['table'] = 'analysis'
        else:
            topics[obj['_id']]['table'] = tsplit[0]


INSERT_TOPIC_QUERY = """INSERT INTO historian.{} (id, name, data_table)
                          VALUES(?, ?, ?)
                          ON DUPLICATE KEY UPDATE name=name, data_table=data_table
                        """.format('topic')

INSERT_DATA_QUERY = """INSERT INTO historian.{} (topic_id, ts, result)
                      VALUES(?, ?, ?)
                      ON DUPLICATE KEY UPDATE result=result
                    """


def insert_topic(cursor, id, name, data_table, flush=False):
    global total_time
    global batch

    batch.append((id, name, data_table))
    if len(batch) > 1000 or flush:
        cursor.executemany(INSERT_TOPIC_QUERY, batch)
        total_time += cursor.duration
        batch = []


# def insert_crate_data(cursor,table_name, topic_id, ts, data):
#     global total_time
#     global batch_table_name
#
#     ts_formatted = utils.format_timestamp(ts)
#     insert_query = INSERT_DATA_QUERY.format(table_name)
#
#     if table_name in ('analysis', 'datalogger', 'device'):
#         if not isinstance(data, int) and not isinstance(data, float):
#             insert_errors.write("table: {} topic: {} ts: {} data: {}".format(
#                 table_name, topic_id, ts, data))
#             return
#
#     the_batch = batch_table_name[table_name]
#     the_batch.append((topic_id, ts, data))
#
#     if len(the_batch) > 1000:
#         try:
#             results = cursor.executemany(insert_query, the_batch)
#         except ProgrammingError as e:
#             insert_errors.write(str(e))
#         total_time += cursor.duration
#         batch_table_name[table_name] = []

crate_created = False


def get_crate_db():
    global crate_created
    crate_db = crate_client.connect(crate_params["connection"]["params"]["host"],
                                    error_trace=True)
    if not crate_created:
        cratedriver.create_schema(crate_db)
        crate_created = True
    return crate_db


def insert_topics_to_crate():
    global total_time

    crate_db = get_crate_db()
    cursor = crate_db.cursor()
    inserted = 0
    for mongo_id, obj in topics.items():
        insert_topic(cursor, obj["hash"], obj["name"], obj['table'])
        inserted += 1
        if inserted % 1000 == 0:
            print("Inserted topic {} in {}ms".format(inserted, total_time))

    if len(batch) > 0:
        cursor.executemany(INSERT_TOPIC_QUERY, batch)
        total_time += cursor.duration


def insert_from_queue(insertion_queue, inserted_metrics_queue, logging_queue):
    internal = []
    insert_query = INSERT_DATA_QUERY.format(insertion_queue.table_name)
    print('Starting queue for: {}'.format(insertion_queue.table_name))

    while True:
        item = insertion_queue.get(block=True)
        if item == "done":
            break
        internal.append(item)
        if len(internal) >= 1000:
            try:
                conn = get_crate_db()
                cursor = conn.cursor()
                cursor.executemany(insert_query, internal)
                inserted_metrics_queue.put((len(internal), cursor.duration))
                cursor.close()
                conn.close()
                internal = []
            except Exception as ex:
                logging_queue.put('An excption occured for {} {}'.format(
                    insertion_queue.table_name, ex.message))
                sys.stderr.write('Exception 1: {}'.format(ex.message))

    if len(internal) > 0:
        try:
            conn = get_crate_db()
            cursor = conn.cursor()
            cursor.executemany(insert_query, internal)
            inserted_metrics_queue.put((len(internal), cursor.duration))
            internal = []
            cursor.close()
        except Exception as ex:
            sys.stderr.write('Exception 2: {}'.format(ex.message))
    print('Ending queue for: {}'.format(insertion_queue.table_name))

insert_threads = []
metric_queue = Queue.Queue()
logger_queue = Queue.Queue()

for q in table_queues.values():

    insert_thread = Thread(target=insert_from_queue, args=[q, metric_queue,
                                                           logger_queue])
    insert_thread.daemon = True
    insert_thread.start()
    insert_threads.append(insert_thread)


def log_write(queue):
    with open("errors.txt", "w") as ferr:
        try:
            while True:
                item = queue.get(block=True)
                ferr.write("{}\n".format(str(item)))
        except Exception as ex:
            sys.stderr.write("Logger exception: {}".format(str(ex)))

logger_thread = Thread(target=log_write, args=[logger_queue])


def start_transfer_data():
    mongo_db = get_mongo_db()
    total_time = 0
    added_to_queue = 0
    current_topic_id = None
    last_timestamp = None

    try:
        total_data = mongo_db.data.count()
        print('Total data: {}'.format(total_data))
        result = mongo_db.data.find({}).sort([('ts', pymongo.ASCENDING)]).limit(1).next()
        print('Before: {}'.format(result['ts']))
        last_timestamp = result['ts'] - timedelta(days=1)
        print('After: {}'.format(result['ts']))

        for obj in mongo_db.data.find({'ts': {"$gt": last_timestamp}}, no_cursor_timeout=True).sort([
            ('ts', pymongo.ASCENDING)
        ]):
            if obj['topic_id'] not in topics:
                _log.error("MISSING topic_id {} in data table".format(obj['topic_id']))
                continue

            current_topic_id = obj['topic_id']
            if last_timestamp is None or current_topic_id is None or obj['value'] is None:
                print('ITS NONE for: id: {} ts {} tid: {} data: {}'.format(
                    obj['_id'], obj['ts'], current_topic_id, obj['value']))
                continue
            last_timestamp = obj['ts']

            topic_obj = topics[obj['topic_id']]
            if topic_obj['table'] in ('analysis', 'datalogger', 'device'):
                    if not isinstance(obj['value'], int) and not isinstance(obj['value'], float):
                        logger_queue.put("table: {} topic: {} ts: {} data: {}".format(
                            topic_obj['table'], obj['topic_id'], obj['ts'], obj['value']))
                        continue

            table_queues[topic_obj['table']].put((topic_obj['hash'],
                                                 utils.format_timestamp(obj['ts']),
                                                 obj['value']))

            # insert_crate_data(cursor, topic_obj['table'], topic_obj['hash'],
            # obj['ts'], obj['value'])
            added_to_queue += 1
            if added_to_queue % 5000 == 0:
                print("Added to queue data {} {} in {}ms".format(
                    topic_obj['table'],
                    added_to_queue,
                    total_time))
    except Exception as ex:
        logger_queue.put(ex.message)
        with open('last_data.txt', 'w') as lf:
            lf.write("{},{}".format(current_topic_id, last_timestamp))




build_topics_mapping()
insert_topics_to_crate()
start_transfer_data()

for q in table_queues.values():
    q.put("done")
print('Total data insertion time: {}ms'.format(total_time))

while len(insert_threads) > 0:
    try:
        for i in range(len(insert_threads) - 1, 0, -1):
            if not insert_threads[i].is_alive():
                print('Removing thread: {}'.format(i))
                insert_threads.remove(i)

    except ValueError:
        pass
    finally:
        sleep(0.1)
