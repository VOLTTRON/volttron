import os

from gevent import subprocess
import pytest
from datetime import datetime
from pytz import UTC

from volttron.platform.agent.base_historian import BackupDatabase, BaseHistorian


def test_get_outstanding_to_publish_should_return_records(backup_database):
    init_db(backup_database)
    expected_records = [
        {
            "_id": 1,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, tzinfo=UTC),
            "topic": "foobar_topic0",
            "value": 4242,
        },
        {
            "_id": 2,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 1, tzinfo=UTC),
            "topic": "foobar_topic1",
            "value": 4243,
        },
        {
            "_id": 3,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 2, tzinfo=UTC),
            "topic": "foobar_topic2",
            "value": 4244,
        },
    ]

    actual_records = backup_database.get_outstanding_to_publish(1000)

    assert actual_records == expected_records
    assert backup_database._record_count == len(expected_records)


def test_get_outstanding_to_publish_should_return_unique_records_when_duplicates_in_db(
    backup_database,
):
    init_db_with_dupes(backup_database)
    expected_record_count = 8
    expected_records = [
        {
            "_id": 1,
            "headers": {},
            "meta": {},
            "source": "dupesource",
            "timestamp": datetime(2020, 6, 1, 12, 30, 59, tzinfo=UTC),
            "topic": "dupetopic",
            "value": 123,
        },
        {
            "_id": 4,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, tzinfo=UTC),
            "topic": "foobar_topic0",
            "value": 4242,
        },
        {
            "_id": 5,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 1, tzinfo=UTC),
            "topic": "foobar_topic1",
            "value": 4243,
        },
        {
            "_id": 6,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 2, tzinfo=UTC),
            "topic": "foobar_topic2",
            "value": 4244,
        },
        {
            "_id": 7,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 3, tzinfo=UTC),
            "topic": "foobar_topic3",
            "value": 4245,
        },
        {
            "_id": 8,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 4, tzinfo=UTC),
            "topic": "foobar_topic4",
            "value": 4244,
        },
    ]

    actual_records = backup_database.get_outstanding_to_publish(1000)

    assert actual_records == expected_records
    assert backup_database._record_count == expected_record_count


def test_remove_successfully_published_should_clear_cache(backup_database):
    init_db(backup_database)
    cache_before_update = [
        "1|2020-06-01 12:31:00|foobar_source|1|4242|{}",
        "2|2020-06-01 12:31:01|foobar_source|2|4243|{}",
        "3|2020-06-01 12:31:02|foobar_source|3|4244|{}",
    ]

    assert get_all_data("outstanding") == cache_before_update
    assert backup_database._record_count == len(cache_before_update)

    orig_record_count = backup_database._record_count
    successful_publishes = set((None,))
    submit_size = 1000  # This is the default size given by BaseHistorianAgent

    backup_database.remove_successfully_published(successful_publishes, submit_size)

    assert get_all_data("outstanding") == []
    current_record_count = backup_database._record_count
    assert current_record_count < orig_record_count
    assert current_record_count == 0


def test_remove_successfully_published_should_keep_duplicates_in_cache(backup_database):
    init_db_with_dupes(backup_database)
    orig_record_count = backup_database._record_count
    cache_before_update = [
        "1|2020-06-01 12:30:59|dupesource|1|123|{}",
        "2|2020-06-01 12:30:59|dupesource|1|123|{}",
        "3|2020-06-01 12:30:59|dupesource|1|123|{}",
        "4|2020-06-01 12:31:00|foobar_source|2|4242|{}",
        "5|2020-06-01 12:31:01|foobar_source|3|4243|{}",
        "6|2020-06-01 12:31:02|foobar_source|4|4244|{}",
        "7|2020-06-01 12:31:03|foobar_source|5|4245|{}",
        "8|2020-06-01 12:31:04|foobar_source|6|4244|{}",
    ]
    assert get_all_data("outstanding") == cache_before_update

    #  modifying these attributes of the backup_database to simulate that we found duplicates upon getting duplicate records from the outstanding table
    backup_database._dupe_ids = [2, 3]
    backup_database._dedupe_ids = [1, 4, 5, 6, 7, 8]
    expected_cache_after_update = [
        "2|2020-06-01 12:30:59|dupesource|1|123|{}",
        "3|2020-06-01 12:30:59|dupesource|1|123|{}",
    ]
    successful_publishes = set((None,))
    submit_size = 1000  # This is the default size given by BaseHistorianAgent

    backup_database.remove_successfully_published(successful_publishes, submit_size)

    assert get_all_data("outstanding") == expected_cache_after_update
    current_record_count = backup_database._record_count
    assert current_record_count < orig_record_count
    assert current_record_count == len(expected_cache_after_update)


def init_db_with_dupes(backup_database):
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
            "source": "dupesource",
            "topic": "dupetopic",
            "meta": {},
            "readings": [("2020-06-01 12:30:59", 123)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic0",
            "meta": {},
            "readings": [("2020-06-01 12:31:00", 4242)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic1",
            "meta": {},
            "readings": [("2020-06-01 12:31:01", 4243)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic2",
            "meta": {},
            "readings": [("2020-06-01 12:31:02", 4244)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic3",
            "meta": {},
            "readings": [("2020-06-01 12:31:03", 4245)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic4",
            "meta": {},
            "readings": [("2020-06-01 12:31:04", 4244)],
            "headers": {},
        },
    ]
    backup_database.backup_new_data(new_publish_list)


def init_db(backup_database):
    new_publish_list = [
        {
            "source": "foobar_source",
            "topic": "foobar_topic0",
            "meta": {},
            "readings": [("2020-06-01 12:31:00", 4242)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic1",
            "meta": {},
            "readings": [("2020-06-01 12:31:01", 4243)],
            "headers": {},
        },
        {
            "source": "foobar_source",
            "topic": "foobar_topic2",
            "meta": {},
            "readings": [("2020-06-01 12:31:02", 4244)],
            "headers": {},
        },
    ]
    backup_database.backup_new_data(new_publish_list)


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
