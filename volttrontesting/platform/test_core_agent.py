import logging

import gevent
import pytest
from dateutil.parser import parse as dateparse
from zmq.utils import jsonapi as json

from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD, \
    STATUS_UNKNOWN


@pytest.mark.agent
def test_agent_status_set_when_created(volttron_instance1):
    agent = volttron_instance1.build_agent()
    assert agent.vip.health.get_status() is not None
    assert isinstance(agent.vip.health.get_status(), str)
    l = json.loads(agent.vip.health.get_status())
    assert l['status'] == STATUS_GOOD
    assert l['context'] is None


@pytest.mark.agent
def test_agent_status_changes(volttron_instance1):
    unknown_message = "This is unknown"
    bad_message = "Bad kitty"
    agent = volttron_instance1.build_agent()
    agent.vip.health.set_status(STATUS_UNKNOWN, unknown_message)
    r = json.loads(agent.vip.health.get_status())
    assert unknown_message == r['context']
    assert STATUS_UNKNOWN == r['status']

    agent.vip.health.set_status(STATUS_BAD, bad_message)
    r = json.loads(agent.vip.health.get_status())
    assert bad_message == r['context']
    assert STATUS_BAD == r['status']


@pytest.mark.agent
def test_agent_last_update_increases(volttron_instance1):
    agent = volttron_instance1.build_agent()
    s = json.loads(agent.vip.health.get_status())
    dt = dateparse(s['last_updated'], fuzzy=True)
    agent.vip.health.set_status(STATUS_UNKNOWN, 'Unknown now!')
    gevent.sleep(1)
    s = json.loads(agent.vip.health.get_status())
    dt2 = dateparse(s['last_updated'], fuzzy=True)
    assert dt < dt2