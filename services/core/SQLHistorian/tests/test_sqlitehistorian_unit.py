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
    # Uniqeness is defined as a combination of topic and timestamp
    # Thus a duplicate has the same topic and timestamp
    for num in range(42, 45):
        sql_historian._capture_record_data(
            peer=None,
            sender=None,
            bus=None,
            topic="foobar",
            headers={
                "Date": "2015-11-17 21:24:10.189393+00:00",
                "TimeStamp": "2015-11-17 21:24:10.189393+00:00",
            },
            message=num,
        )

    # Add unique records to queue
    for num in range(5, 8):
        sql_historian._capture_record_data(
            peer=None,
            sender=None,
            bus=None,
            topic=f"roma{num}",
            headers={
                "Date": f"2020-11-17 21:2{num}:10.189393+00:00",
                "TimeStamp": f"2020-11-17 21:2{num}:10.189393+00:00",
            },
            message=666,
        )

    sql_historian._retry_period = (
        1
    )  # default is 300 seconds or 5 minutes; setting to 1 second so tests don't take so long
    sql_historian._max_time_publishing = timedelta(
        float(1)
    )  # when SQLHistorian is normally started on the platform, this attribute is set. Since this is a unitish test, setting this manually test can run
    sql_historian.start_process_thread()
    sleep(
        3
    )  # give time for all databases to initialize and historian to process workflow

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
