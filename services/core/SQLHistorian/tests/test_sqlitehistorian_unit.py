import os
import subprocess
from shutil import rmtree
from datetime import timedelta
from gevent import sleep

import pytest

from services.core.SQLHistorian.sqlhistorian import historian

CACHE_NAME = "backup.sqlite"
HISTORIAN_DB = "./data/historian.sqlite"


def test_historian_should_filter_duplicates(sql_historian):
    # Add duplicates to queue
    # Uniqueness is defined as a combination of topic and timestamp
    # Thus a duplicate has the same topic and timestamp
    for num in range(40, 43):
        sql_historian._capture_record_data(
            peer=None,
            sender=None,
            bus=None,
            topic="duplicate_topic",
            headers={
                "Date": "2015-11-17 21:24:10.189393+00:00",
                "TimeStamp": "2015-11-17 21:24:10.189393+00:00",
            },
            message=f"last_duplicate_{num}",
        )

    # Add unique records to queue
    for num in range(2, 5):
        sql_historian._capture_record_data(
            peer=None,
            sender=None,
            bus=None,
            topic=f"unique_record_topic{num}",
            headers={
                "Date": f"2020-11-17 21:2{num}:10.189393+00:00",
                "TimeStamp": f"2020-11-17 21:2{num}:10.189393+00:00",
            },
            message=f"unique_record_{num}",
        )

    # default is 300 seconds/5 minutes;
    # setting to 1 second so tests don't take so long
    sql_historian._retry_period = 1
    # When SQLHistorian is started, this attribute is set.
    # Since the SQLHistorian is being tested without the volttron platform,
    # this attribute must be set so that the test can run
    sql_historian._max_time_publishing = timedelta(float(1))

    sql_historian.start_process_thread()
    # give time for databases to initialize and historian to start workflow
    sleep(3)

    assert query_db("""select * from outstanding""", CACHE_NAME) == ""
    # check that historian saves last duplicate from cache in the "data" table
    assert '2015-11-17T21:24:10.189393+00:00|1|"last_duplicate_42"' in \
           query_db("""select * from data""", HISTORIAN_DB).split()
    # check that historian saves only one duplicate in the "topics" table
    assert "1|duplicate_topic" in \
           query_db("""select * from topics""", HISTORIAN_DB).split()


@pytest.fixture()
def sql_historian():
    config = {"connection":
                  {"type": "sqlite", "params": {"database": HISTORIAN_DB}}}

    yield historian.historian(config)

    # Teardown
    # backup sqlite database has name "backup.sqlite".
    # database is created if it doesn't exist;
    # see the method: BackupDatabase._setupdb(check_same_thread) for details
    # also, delete the historian database for this test, which is an sqlite
    # database in folder /data
    if os.path.exists("./data"):
        rmtree("./data")
    if os.path.exists(CACHE_NAME):
        os.remove(CACHE_NAME)


def query_db(query, database):
    try:
        output = subprocess.run(["sqlite3", database, query],
                                text=True, capture_output=True, check=True)
    except subprocess.CalledProcessError as exception:
        print(exception)
    return output.stdout


def get_tables(database):
    result = query_db(""".tables""", database)
    res = set(result.replace("\n", "").split())
    return res
