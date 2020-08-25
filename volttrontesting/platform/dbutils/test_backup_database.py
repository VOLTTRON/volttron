import os

from gevent import subprocess
import pytest
from datetime import datetime
from pytz import UTC

from volttron.platform.agent.base_historian import BackupDatabase, BaseHistorian


def test_backup_new_data_should_filter_duplicates(backup_database):
    new_publish_list = [
        {
            "source": "dupesource",
            "topic": "dupetopic",
            "meta": {},
            "readings": [("2020-06-01 12:30:59", 123)],
            "headers": {},
        },
        {
            "source": "dupesource",
            "topic": "dupetopic",
            "meta": {},
            "readings": [("2020-06-01 12:30:59", 123)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic",
            "meta": {},
            "readings": [("2020-05-25 08:46:00", 846)],
            "headers": {},
        },
    ]
    backup_database.backup_new_data(new_publish_list)
    orig_record_count = backup_database._record_count

    expected_results = [
        {
            "_id": 3,
            "timestamp": datetime(2020, 5, 25, 8, 46, tzinfo=UTC),
            "source": "foobar_source",
            "topic": "foobar_topic",
            "value": 846,
            "headers": {},
            "meta": {},
        },
        {
            "_id": 1,
            "timestamp": datetime(2020, 6, 1, 12, 30, 59, tzinfo=UTC),
            "source": "dupesource",
            "topic": "dupetopic",
            "value": 123,
            "headers": {},
            "meta": {},
        },
    ]
    expected_cache = [
        "1|2020-06-01 12:30:59|dupesource|1|123|{}",
        "3|2020-05-25 08:46:00|foobar_source|2|846|{}",
    ]
    expected_record_count = 2

    actual_results = backup_database.get_outstanding_to_publish(10)
    current_record_count = backup_database._record_count

    assert actual_results == expected_results
    assert get_all_data("outstanding") == expected_cache
    assert current_record_count < orig_record_count
    assert current_record_count == expected_record_count


@pytest.fixture()
def backup_database():
    yield BackupDatabase(BaseHistorian(), None, 0.9)

    # Teardown
    # the backup database is an sqlite database with the name "backup.sqlite".
    # the db is created if it doesn't exist; see the method: BackupDatabase._setupdb(check_same_thread) for details
    if os.path.exists("./backup.sqlite"):
        os.remove("./backup.sqlite")


def get_all_data(table):
    q = f"""SELECT * FROM {table}"""
    res = query_db(q)
    return res.splitlines()


def query_db(query):
    output = subprocess.run(
        ["sqlite3", "backup.sqlite", query], text=True, capture_output=True
    )
    # check_returncode() will raise a CalledProcessError if the query fails
    # see https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.returncode
    output.check_returncode()

    return output.stdout
