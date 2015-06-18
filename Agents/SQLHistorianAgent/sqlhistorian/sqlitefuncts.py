import errno
import os
import sqlite3

__database = None
__detect_types = None

def prepare(database, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES):
    global __database, __detect_types
    if database == ':memory:':
        __database = ':memory:'
    else:
        __database = os.path.expanduser(database)
        db_dir  = os.path.dirname(__database)

        #If the db does not exist create it
        # in case we are started before the historian.
        try:
            os.makedirs(db_dir)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                raise
        try:
            __detect_types = eval(detect_types)
        except TypeError:
            __detect_types = detect_types

        conn = connect()
        execute('''CREATE TABLE IF NOT EXISTS data
                                (ts timestamp NOT NULL,
                                 topic_id INTEGER NOT NULL,
                                 value_string TEXT NOT NULL,
                                 UNIQUE(ts, topic_id))''',
                conn, False)

        execute('''CREATE INDEX IF NOT EXISTS data_idx
                                ON data (ts ASC)''',
                conn, False)

        execute('''CREATE TABLE IF NOT EXISTS topics
                                (topic_id INTEGER PRIMARY KEY,
                                 topic_name TEXT NOT NULL,
                                 UNIQUE(topic_name))''',
                conn, True)

def execute(query, connection=None, commit=True):
    if not connection:
        connection = connect()
    connection.execute(query)
    if commit:
        connection.commit()



def connect():
    if __database is None:
        raise AttributeError
    if __detect_types:
        return sqlite3.connect(__database, detect_types=__detect_types)
    return sqlite3.connect(__database)

def query_topics(connection=None):
    if not connection:
        connection = connect()

    c = connection.cursor()
    c.execute("SELECT * FROM topics")

    while True:
        results = c.fetchmany(1000)
        if not results:
            break
        for result in results:
            yield result
