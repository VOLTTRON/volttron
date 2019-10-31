
import subprocess
import gevent
import pytest
from dateutil.parser import parse as dateparse

from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD, \
    STATUS_UNKNOWN
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform import jsonapi


@pytest.mark.agent
def test_agent_can_get_platform_version(volttron_instance):
    agent = volttron_instance.build_agent()
    query = Query(agent.core)
    response = subprocess.check_output(['volttron', "--version"],
                                       stderr=subprocess.STDOUT, universal_newlines=True)
    assert response.strip()
    _, version = response.strip().split(" ")

    platform_version = query.query("platform-version")
    assert version == platform_version.get(timeout=2)


@pytest.mark.agent
def test_agent_status_set_when_created(volttron_instance):
    agent = volttron_instance.build_agent()
    assert agent.vip.health.get_status() is not None
    assert isinstance(agent.vip.health.get_status(), dict)
    l = agent.vip.health.get_status()
    assert l['status'] == STATUS_GOOD
    assert l['context'] is None

    assert isinstance(agent.vip.health.get_status_json(), str)
    l = jsonapi.loads(agent.vip.health.get_status_json())
    assert l['status'] == STATUS_GOOD
    assert l['context'] is None

    assert agent.vip.health.get_status_value() == STATUS_GOOD


@pytest.mark.agent
def test_agent_status_changes(volttron_instance):
    unknown_message = "This is unknown"
    bad_message = "Bad kitty"
    agent = volttron_instance.build_agent()
    agent.vip.health.set_status(STATUS_UNKNOWN, unknown_message)
    r = agent.vip.health.get_status()
    assert unknown_message == r['context']
    assert STATUS_UNKNOWN == r['status']

    agent.vip.health.set_status(STATUS_BAD, bad_message)
    r = agent.vip.health.get_status()
    assert bad_message == r['context']
    assert STATUS_BAD == r['status']


@pytest.mark.agent
def test_agent_last_update_increases(volttron_instance):
    agent = volttron_instance.build_agent()
    s = agent.vip.health.get_status()
    dt = dateparse(s['last_updated'], fuzzy=True)
    agent.vip.health.set_status(STATUS_UNKNOWN, 'Unknown now!')
    gevent.sleep(1)
    s = agent.vip.health.get_status()
    dt2 = dateparse(s['last_updated'], fuzzy=True)
    assert dt < dt2
