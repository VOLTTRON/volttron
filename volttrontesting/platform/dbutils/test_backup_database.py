import os
import pytest

from gevent import subprocess
from datetime import datetime
from pytz import UTC

from volttron.platform.agent.base_historian import BackupDatabase, BaseHistorian

SIZE_LIMIT = 1000  # the default submit_size_limit for BaseHistorianAgents


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
            "value": 42,
        },
        {
            "_id": 2,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 1, tzinfo=UTC),
            "topic": "foobar_topic1",
            "value": 43,
        },
        {
            "_id": 3,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, 2, tzinfo=UTC),
            "topic": "foobar_topic2",
            "value": 44,
        },
    ]

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records
    assert backup_database._record_count == len(expected_records)


def test_get_outstanding_to_publish_should_return_unique_records_when_duplicates_in_db(
    backup_database,
):
    init_db_with_dupes(backup_database)
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

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records
    assert backup_database._record_count == len(new_publish_list_dupes)


def test_remove_successfully_published_should_clear_cache(backup_database):
    init_db(backup_database)
    cache_before_update = [
        "1|2020-06-01 12:31:00|foobar_source|1|42|{}",
        "2|2020-06-01 12:31:01|foobar_source|2|43|{}",
        "3|2020-06-01 12:31:02|foobar_source|3|44|{}",
    ]

    assert get_all_data("outstanding") == cache_before_update
    assert backup_database._record_count == len(cache_before_update)

    orig_record_count = backup_database._record_count

    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)

    assert get_all_data("outstanding") == []
    current_record_count = backup_database._record_count
    assert current_record_count < orig_record_count
    assert current_record_count == 0


def test_remove_successfully_published_should_keep_duplicates_in_cache(backup_database):
    init_db_with_dupes(backup_database)
    orig_record_count = backup_database._record_count
    cache_before_update = [
        "1|2020-06-01 12:30:59|dupesource|1|123|{}",
        "2|2020-06-01 12:30:59|dupesource|1|456|{}",
        "3|2020-06-01 12:30:59|dupesource|1|789|{}",
        "4|2020-06-01 12:31:00|foobar_source|2|4242|{}",
        "5|2020-06-01 12:31:01|foobar_source|3|4243|{}",
        "6|2020-06-01 12:31:02|foobar_source|4|4244|{}",
        "7|2020-06-01 12:31:03|foobar_source|5|4245|{}",
        "8|2020-06-01 12:31:04|foobar_source|6|4244|{}",
    ]
    assert get_all_data("outstanding") == cache_before_update

    expected_cache_after_update = [
        "2|2020-06-01 12:30:59|dupesource|1|456|{}",
        "3|2020-06-01 12:30:59|dupesource|1|789|{}",
    ]

    backup_database.get_outstanding_to_publish(SIZE_LIMIT)
    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)

    assert get_all_data("outstanding") == expected_cache_after_update
    current_record_count = backup_database._record_count
    assert current_record_count < orig_record_count
    assert current_record_count == 2


def test_get_outstanding_to_publish_should_return_unique_records_on_multiple_trans(
    backup_database,
):
    init_db_with_dupes(backup_database)
    cache_before_update = [
        "1|2020-06-01 12:30:59|dupesource|1|123|{}",
        "2|2020-06-01 12:30:59|dupesource|1|456|{}",
        "3|2020-06-01 12:30:59|dupesource|1|789|{}",
        "4|2020-06-01 12:31:00|foobar_source|2|4242|{}",
        "5|2020-06-01 12:31:01|foobar_source|3|4243|{}",
        "6|2020-06-01 12:31:02|foobar_source|4|4244|{}",
        "7|2020-06-01 12:31:03|foobar_source|5|4245|{}",
        "8|2020-06-01 12:31:04|foobar_source|6|4244|{}",
    ]
    assert get_all_data("outstanding") == cache_before_update

    # First transaction
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

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records

    # Second transaction
    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)
    expected_records = [
        {
            "_id": 2,
            "headers": {},
            "meta": {},
            "source": "dupesource",
            "timestamp": datetime(2020, 6, 1, 12, 30, 59, tzinfo=UTC),
            "topic": "dupetopic",
            "value": 456,
        }
    ]

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records

    # Third transaction
    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)
    expected_records = [
        {
            "_id": 3,
            "headers": {},
            "meta": {},
            "source": "dupesource",
            "timestamp": datetime(2020, 6, 1, 12, 30, 59, tzinfo=UTC),
            "topic": "dupetopic",
            "value": 789,
        }
    ]

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records

    # Fourth Transaction
    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)
    assert backup_database.get_outstanding_to_publish(SIZE_LIMIT) == []


new_publish_list_dupes = [
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
        "readings": [("2020-06-01 12:30:59", 456)],
        "headers": {},
    },
    {
        "source": "dupesource",
        "topic": "dupetopic",
        "meta": {},
        "readings": [("2020-06-01 12:30:59", 789)],
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


def init_db_with_dupes(backup_database):
    backup_database.backup_new_data(new_publish_list_dupes)


new_publish_list_unique = [
    {
        "source": "foobar_source",
        "topic": "foobar_topic0",
        "meta": {},
        "readings": [("2020-06-01 12:31:00", 42)],
        "headers": {},
    },
    {
        "source": "foobar_source",
        "topic": "foobar_topic1",
        "meta": {},
        "readings": [("2020-06-01 12:31:01", 43)],
        "headers": {},
    },
    {
        "source": "foobar_source",
        "topic": "foobar_topic2",
        "meta": {},
        "readings": [("2020-06-01 12:31:02", 44)],
        "headers": {},
    },
]


def init_db(backup_database):
    backup_database.backup_new_data(new_publish_list_unique)


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
