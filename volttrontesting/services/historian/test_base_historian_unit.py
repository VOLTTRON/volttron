import datetime
from datetime import timedelta
import os
from shutil import rmtree
from time import sleep

import pytest
from pytz import UTC

from utils.utils import AgentMock
from volttron.platform.agent.base_historian import BaseHistorianAgent, Agent

CACHE_NAME = "backup.sqlite"
HISTORIAN_DB = "./data/historian.sqlite"


def test_base_historian_agent_should_filter_duplicates(base_historian_agent):
    # Add duplicates to queue
    # Uniqueness is defined as a combination of topic and timestamp
    # Thus a duplicate has the same topic and timestamp
    for num in range(40, 43):
        base_historian_agent._capture_record_data(
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
        base_historian_agent._capture_record_data(
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

    # Since this is a unit test, we have to "manually start" the base_historian to get the workflow going
    base_historian_agent.start_process_thread()
    # Adding sleep to ensure that all data gets publised in the cache before testing
    sleep(3)

    expected_to_publish_list = [
        {
            "_id": 3,
            "timestamp": datetime.datetime(
                2015, 11, 17, 21, 24, 10, 189393, tzinfo=UTC
            ),
            "source": "record",
            "topic": "duplicate_topic",
            "value": "last_duplicate_42",
            "headers": {
                "Date": "2015-11-17 21:24:10.189393+00:00",
                "TimeStamp": "2015-11-17 21:24:10.189393+00:00",
                "time_error": False
            },
            "meta": {},
        }
    ]


    # When the base_historian is handling duplicates from the cache, the base_historian is expected to make multiple calls to publish_to_historian
    # in which each call contains exactly one duplicate record. More importanly, the base_historian is also expected to make each call to publish_to_historian
    # in the order in which the duplicates were initially inserted into the cache (i.e. First-in, First Out, FIFO)
    # In this specific case, we have three duplicates that need to be processed. Thus, publish_to_historian will get called thrice.
    # On the first call, publish_to_historian will publish 'unique_record_2', 'unique_record_3', 'unique_record_4' AND  'last_duplicate_40'
    # On the second call, publish_to_historian will publish last_duplicate_41
    # On the third and final call, publish_to_historian will publish last_duplicate_42
    # Since it is difficult to validate every call except the last call, we will simply validate that the last call
    # did indeed publish exactly one duplicate record that was the last duplicate record inserted into the cache.
    assert base_historian_agent.last_to_publish_list == expected_to_publish_list


BaseHistorianAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


class BaseHistorianAgentTestWrapper(BaseHistorianAgent):
    def __init__(self, **kwargs):
        self.last_to_publish_list = ""
        super(BaseHistorianAgentTestWrapper, self).__init__(**kwargs)

    def publish_to_historian(self, to_publish_list):
        self.report_all_handled()
        self.last_to_publish_list = to_publish_list


@pytest.fixture()
def base_historian_agent():
    base_historian = BaseHistorianAgentTestWrapper()
    # default is 300 seconds or 5 minutes; setting to 1 second so tests don't take so long
    base_historian._retry_period = 1.0
    # When SQLHistorian is normally started on the platform, this attribute is set.
    # Since the SQLHistorian is being tested without the volttron platform,
    # this attribute must be set so that the test can run
    base_historian._max_time_publishing = timedelta(float(1))

    yield base_historian
    # Teardown
    # the backup database is an sqlite database with the name "backup.sqlite".
    # the db is created if it doesn't exist; see the method: BackupDatabase._setupdb(check_same_thread) for details
    # also, delete the historian database for this test, which is an sqlite db in folder /data
    if os.path.exists("./data"):
        rmtree("./data")
    if os.path.exists(CACHE_NAME):
        os.remove(CACHE_NAME)
