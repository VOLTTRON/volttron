from datetime import datetime

import pytest
import mock

from volttron.platform.agent import utils
from volttron.platform.messaging import headers as header_mod
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.base_historian import BaseHistorianAgent, BaseQueryHistorianAgent, BackupDatabase
from volttron.platform.vip.agent.results import AsyncResult
# need import so that we can mock it.
from volttron.platform.vip.agent.subsystems.query import Query
from volttrontesting.utils.utils import AgentMock
from time import sleep


class QueryHelper:
    """
    Query helper allows us to mock out the Query subsystem and return default
    values for calls to it.
    """

    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result('my_instance_name')
        return result


# Mock our base historian subsystems
BaseHistorianAgent.__bases__ = (AgentMock.imitate(Agent, Agent()),)


class ConcreteHistorianAgent(BaseHistorianAgent):
    def __init__(self, **kwargs):
        super(ConcreteHistorianAgent, self).__init__(**kwargs)
        self._published_list_items = []
        self.start_process_thread()
        sleep(0.5)

    def publish_to_historian(self, to_publish_list):
        self._published_list_items.append(to_publish_list)

    def get_publish_list(self):
        return self._published_list_items

    def reset_publish_list_items(self):
        self._published_list_items.clear()

    def has_published_items(self):
        return len(self._published_list_items) > 0


def test_cache_only_default_and_invalid():
    """
    Make sure that the agent is able to determine whether or not cache only is available as a function call and that
    the value gets transferred to the variable
    """
    agent = BaseHistorianAgent(cache_only_enabled=True)
    assert agent is not None
    assert agent.is_cache_only_enabled()

    agent = BaseHistorianAgent()
    assert agent is not None
    assert not agent.is_cache_only_enabled()

    # Value error should be raised for this
    with pytest.raises(ValueError) as e:
        agent = BaseHistorianAgent(cache_only_enabled="Blah")
        assert e.value == f"cache_only_enabled should be either True or False"


# mock MUST patch where the target is imported not the path to where the code lies.
@mock.patch(target='volttron.platform.agent.base_historian.Query', new=QueryHelper)
def test_enable_and_disable_cache_only_through_config_store():
    agent = BaseHistorianAgent()
    agent._configure("config", "UPDATE", dict(cache_only_enabled=True))
    assert agent.is_cache_only_enabled()

    agent._configure("config", "UPDATE", dict(cache_only_enabled=False))
    assert not agent.is_cache_only_enabled()

    # Should not update as Blah is not True or FalseValue error should be raised for this
    agent._configure("config", "UPDATE", dict(cache_only_enabled="Blah"))

    # Make sure the update didn't get transferred to the state
    assert not agent.is_cache_only_enabled()


def test_cache_enable():
    now = utils.format_timestamp(datetime.utcnow())
    headers = {
        header_mod.DATE: now,
        header_mod.TIMESTAMP: now
    }
    agent = ConcreteHistorianAgent(cache_only_enabled=True)
    assert agent is not None
    device = "devices/testcampus/testbuilding/testdevice"
    agent._capture_data(peer="foo",
                        sender="test",
                        bus="",
                        topic=device,
                        headers=headers,
                        message={"OutsideAirTemperature": 52.5, "MixedAirTemperature": 58.5},
                        device=device
                        )
    sleep(0.1)
    # Should not have published to the concrete historian because we are in cache_only
    assert not agent.has_published_items()

    agent = ConcreteHistorianAgent(cache_only_enabled=False)  # , process_loop_in_greenlet=False)
    agent._capture_data(peer="foo",
                        sender="test",
                        bus="",
                        topic=device,
                        headers=headers,
                        message={"OutsideAirTemperature": 52.5, "MixedAirTemperature": 58.5},
                        device=device
                        )
    sleep(0.1)
    # give a small amount of time so that the queue can get empty
    assert agent.has_published_items()
    assert len(agent.get_publish_list()) == 2
