import os
import pytest
from pathlib import Path
from gevent import subprocess
from datetime import datetime
from pytz import UTC

from volttron.platform.agent.base_historian import BackupDatabase, BaseHistorian

SIZE_LIMIT = 1000  # the default submit_size_limit for BaseHistorianAgents

agent_data_dir = os.path.join(os.getcwd(), os.path.basename(os.getcwd()) + ".agent-data")
cache_db = str(Path(agent_data_dir).joinpath("backup.sqlite"))

def test_get_outstanding_to_publish_should_return_records(
    backup_database, new_publish_list_unique
):
    init_db(backup_database, new_publish_list_unique)
    expected_records = []
    for idx in range(1000):
        data = {
            "_id": idx + 1,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, tzinfo=UTC),
            "topic": f"foobar_topic{idx}",
            "value": idx,
        }
        expected_records.append(data)

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records
    assert backup_database._record_count == len(expected_records)


def test_get_outstanding_to_publish_should_return_unique_records_when_duplicates_in_db(
    backup_database, new_publish_list_dupes
):
    init_db_with_dupes(backup_database, new_publish_list_dupes)
    expected_records = [
        {
            "_id": 1,
            "headers": {},
            "meta": {},
            "source": "dupesource",
            "timestamp": datetime(2020, 6, 1, 12, 30, 59, tzinfo=UTC),
            "topic": "dupetopic",
            "value": 123,
        }
    ]
    for x in range(4, 1000):
        data = {
            "_id": x,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, tzinfo=UTC),
            "topic": f"foobar_topic{x}",
            "value": x,
        }
        expected_records.append(data)

    actual_records = backup_database.get_outstanding_to_publish(SIZE_LIMIT)

    assert actual_records == expected_records
    assert backup_database._record_count == len(new_publish_list_dupes)


def test_remove_successfully_published_should_clear_cache(
    backup_database, new_publish_list_unique
):
    init_db(backup_database, new_publish_list_unique)

    assert backup_database._record_count == len(new_publish_list_unique)

    orig_record_count = backup_database._record_count

    backup_database.get_outstanding_to_publish(SIZE_LIMIT)
    backup_database.remove_successfully_published(set((None,)), SIZE_LIMIT)

    assert get_all_data("outstanding") == []
    current_record_count = backup_database._record_count
    assert current_record_count < orig_record_count
    assert current_record_count == 0


def test_remove_successfully_published_should_keep_duplicates_in_cache(
    backup_database, new_publish_list_dupes
):
    init_db_with_dupes(backup_database, new_publish_list_dupes)
    orig_record_count = backup_database._record_count

    assert len(get_all_data("outstanding")) == len(new_publish_list_dupes)

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
    backup_database, new_publish_list_dupes
):
    init_db_with_dupes(backup_database, new_publish_list_dupes)
    assert len(get_all_data("outstanding")) == len(new_publish_list_dupes)

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
        }
    ]
    for x in range(4, 1000):
        data = {
            "_id": x,
            "headers": {},
            "meta": {},
            "source": "foobar_source",
            "timestamp": datetime(2020, 6, 1, 12, 31, tzinfo=UTC),
            "topic": f"foobar_topic{x}",
            "value": x,
        }
        expected_records.append(data)

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


def init_db_with_dupes(backup_database, new_publish_list_dupes):
    backup_database.backup_new_data(new_publish_list_dupes)


def init_db(backup_database, new_publish_list_unique):
    backup_database.backup_new_data(new_publish_list_unique)


@pytest.fixture(scope="module")
def new_publish_list_unique():
    publish_list_unique = list()
    for idx in range(1000):
        data = {
            "source": "foobar_source",
            "topic": f"foobar_topic{idx}",
            "meta": {},
            "readings": [("2020-06-01 12:31:00", idx)],
            "headers": {},
        }
        publish_list_unique.append(data)

    return tuple(publish_list_unique)


@pytest.fixture(scope="module")
def new_publish_list_dupes():
    dupes = [
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
    ]
    for idx in range(4, 1000):
        data = {
            "source": "foobar_source",
            "topic": f"foobar_topic{idx}",
            "meta": {},
            "readings": [("2020-06-01 12:31:00", idx)],
            "headers": {},
        }
        dupes.append(data)

    return tuple(dupes)


@pytest.fixture()
def backup_database():
    os.makedirs(agent_data_dir, exist_ok=True)
    yield BackupDatabase(BaseHistorian(), None, 0.9)

    # Teardown
    # the backup database is an sqlite database with the name "backup.sqlite".
    # the db is created if it doesn't exist; see the method: BackupDatabase._setupdb(check_same_thread) for details
    if os.path.exists(cache_db):
        os.remove(cache_db)
    if os.path.exists(agent_data_dir):
        os.rmdir(agent_data_dir)


def get_all_data(table):
    q = f"""SELECT * FROM {table}"""
    res = query_db(q)
    return res.splitlines()


def query_db(query):
    output = subprocess.run(
        ["sqlite3", cache_db, query], text=True, capture_output=True
    )
    # check_returncode() will raise a CalledProcessError if the query fails
    # see https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.returncode
    output.check_returncode()

    return output.stdout
