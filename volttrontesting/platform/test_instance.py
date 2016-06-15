from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_ip_and_port
from volttron.platform.vip.agent.subsystems import query


def test_can_handle_platform_name_with_vc_address():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    cfg_entry = "vc|http://{}".format(get_rand_ip_and_port())
    platform_name, vc_address = cfg_entry.split('|')
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, volttron_central_address=cfg_entry)

    assert wrapper.is_running()
    assert wrapper.publickey
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    assert platform_name == q.query(b'platform-name').get(timeout=2)
    assert vc_address == q.query(b'volttron-central-address').get(timeout=2)


def test_can_get_vc_address_from_query():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    vc_address = "http://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, volttron_central_address=vc_address)

    assert wrapper.is_running()
    assert wrapper.publickey
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    assert vc_address == q.query(b'volttron-central-address').get(timeout=2)
    assert None is q.query(b'platform-name').get(timeout=2)
