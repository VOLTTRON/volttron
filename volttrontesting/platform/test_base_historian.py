import pytest
import mock

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
BaseHistorianAgent.__bases__ = (AgentMock.imitate(Agent, Agent()), )


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
    agent = BaseHistorianAgent(cache_only_enabled=True)
    agent._configure("config", "UPDATE", dict(cache_only_enabled=True))
    assert agent.is_cache_only_enabled()

    agent._configure("config", "UPDATE", dict(cache_only_enabled=False))
    assert not agent.is_cache_only_enabled()

    # Should not update as Blah is not True or FalseValue error should be raised for this
    agent._configure("config", "UPDATE", dict(cache_only_enabled="Blah"))

    # Make sure the update didn't get transferred to the state
    assert not agent.is_cache_only_enabled()



