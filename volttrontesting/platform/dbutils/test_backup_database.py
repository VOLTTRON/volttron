import os
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
    actual_results = backup_database.get_outstanding_to_publish(10)

    assert actual_results == expected_results


@pytest.fixture()
def backup_database():
    yield BackupDatabase(BaseHistorian(), None, 0.9)
    if os.path.exists("./backup.sqlite"):
        os.remove("./backup.sqlite")
