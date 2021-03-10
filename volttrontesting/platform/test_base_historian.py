import pytest
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.base_historian import BaseHistorianAgent, BaseQueryHistorianAgent, BackupDatabase
from volttrontesting.utils.utils import AgentMock


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

    # note invalid entry considered False
    agent = BaseHistorianAgent(cache_only_enabled="Blah")
    assert agent is not None
    assert not agent.is_cache_only_enabled()



