import gevent
import pytest
from volttron.platform.agent.utils import parse_timestamp_string


@pytest.mark.subsystems
def test_can_update_status(volttron_instance1):
    new_agent = volttron_instance1.build_agent()
    new_agent.vip.heartbeat.start()
    orig_status = new_agent.vip.health.get_status()
    assert orig_status['current_status'] == 'GOOD'
    assert orig_status['context'] is None
    assert orig_status['utc_last_update'] is not None
    print('original status: {}'.format(orig_status))
    new_context = {'foo': 'A test something when wrong',
                   'woah': ['blah', 'blah']}
    gevent.sleep(1)
    new_agent.vip.health.set_status('BAD', new_context)
    gevent.sleep(1)
    new_status = new_agent.vip.health.get_status()
    print('new status: {}'.format(new_status))
    assert 'BAD' == new_status['current_status']
    assert new_context == new_status['context']
    assert new_status['utc_last_update'] is not None
    old_date = parse_timestamp_string(orig_status['utc_last_update'])
    new_date = parse_timestamp_string(new_status['utc_last_update'])
    assert old_date < new_date
