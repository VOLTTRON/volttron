from volttron.platform.vip.connection import Connection
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_ip_and_port
from volttron.platform.vip.agent.subsystems import query


def test_connection_false_when_instance_dies():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)

    control = Connection(wrapper.local_vip_address, peer='control')
    assert control.is_connected()
    wrapper.shutdown_platform()
    assert not control.is_connected()


def test_connection_false_when_instance_dies():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)

    control = Connection(wrapper.local_vip_address, peer='control')
    assert control.is_connected()
    assert len(control.peers()) > 0


def test_canconnect_to_control():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)

    control = Connection(wrapper.local_vip_address, peer='control')
    agents = control.call('list_agents')
    assert len(agents) == 0


def test_withidentity_can_get_addresses_from_router():
    """
    In order for this test to pass the wrapper must be in encrypted mode.
    :return:
    """
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)
    agent = wrapper.build_agent(identity='test.identity')
    q = query.Query(agent.core)

    # This should never be none.
    response = q.query(b'addresses').get(timeout=2)
    assert len(response) == 1
    assert response[0] == vip_address
    agent.core.stop(timeout=2)
    wrapper.shutdown_platform()


def test_can_get_addresses_from_router():
    """
    In order for this test to pass the wrapper must be in encrypted mode.
    :return:
    """
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    # This should never be none.
    response = q.query(b'addresses').get(timeout=2)
    assert len(response) == 1
    assert response[0] == vip_address
    agent.core.stop(timeout=2)
    wrapper.shutdown_platform()


def test_can_get_serverkey_from_router():
    """
    In order for this test to pass the wrapper must be in encrypted mode.
    :return:
    """
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address, encrypt=True)
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    # This should never be none.
    assert q.query(b'serverkey').get(timeout=2)
    agent.core.stop(timeout=2)
    wrapper.shutdown_platform()


def test_can_get_vc_serverkey_from_router():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address)
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    assert None is q.query(b'volttron-central-serverkey').get(timeout=2)
    agent.core.stop(timeout=2)
    wrapper.shutdown_platform()


def test_can_get_bind_web_address():
    vip_address = "tcp://{}".format(get_rand_ip_and_port())
    wrapper = PlatformWrapper()
    wrapper.startup_platform(vip_address)
    agent = wrapper.build_agent()
    q = query.Query(agent.core)

    assert None is q.query(b'bind-web-address').get(timeout=2)
    agent.core.stop(timeout=2)
    print('DOING SHUTDOWN!')
    wrapper.shutdown_platform(cleanup=False)

    bind_web_address = "http://{}".format(get_rand_ip_and_port())
    print("WEB ADDRESS IS: {}".format(bind_web_address))
    wrapper.startup_platform(vip_address, bind_web_address=bind_web_address)
    agent = wrapper.build_agent()
    q = query.Query(agent.core)
    assert bind_web_address == q.query(b'bind-web-address').get(timeout=2)


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
