import os
from shutil import rmtree
import subprocess

import pytest
from gevent import sleep
from datetime import timedelta
from services.core.SQLHistorian.sqlhistorian import historian

CACHE_NAME = "backup.sqlite"
HISTORIAN_DB = "./data/historian.sqlite"


def test_historian_should_filter_duplicates(sql_historian):
    # Add duplicates to queue
    for i in range(42, 45):
        sql_historian._capture_record_data(
            peer=None,
            sender=None,
            bus=None,
            topic="foobar",
            headers={
                "Date": "2015-11-17 21:24:10.189393+00:00",
                "TimeStamp": "2015-11-17 21:24:10.189393+00:00",
            },
            message=i,
        )

    # Add unique to queue
    sql_historian._capture_record_data(
        peer=None,
        sender=None,
        bus=None,
        topic="roma",
        headers={
            "Date": "2020-11-17 21:24:10.189393+00:00",
            "TimeStamp": "2020-11-17 21:24:10.189393+00:00",
        },
        message=666,
    )

    sql_historian._retry_period = 1
    sql_historian._max_time_publishing = timedelta(float(1))
    sql_historian.start_process_thread()
    sleep(3)

    # make sure that cache is empty
    assert query_db("""select * from outstanding""", CACHE_NAME) == ""

    # check that the historian did publish data in tables
    assert query_db("""select * from data""", HISTORIAN_DB)
    assert query_db("""select * from topics""", HISTORIAN_DB)


@pytest.fixture()
def sql_historian():
    config = {"connection": {"type": "sqlite", "params": {"database": HISTORIAN_DB}}}

    yield historian.historian(config)

    # Teardown
    # the backup database is an sqlite database with the name "backup.sqlite".
    # the db is created if it doesn't exist; see the method: BackupDatabase._setupdb(check_same_thread) for details
    # also, delete the historian database for this test, which is an sqlite db in folder /data
    if os.path.exists("./data"):
        rmtree("./data")
    if os.path.exists(CACHE_NAME):
        os.remove(CACHE_NAME)


def query_db(query, db):
    output = subprocess.run(["sqlite3", db, query], text=True, capture_output=True)
    # check_returncode() will raise a CalledProcessError if the query fails
    # see https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.returncode
    output.check_returncode()
    return output.stdout


def get_tables(db):
    result = query_db(""".tables""", db)
    res = set(result.replace("\n", "").split())
    return res
