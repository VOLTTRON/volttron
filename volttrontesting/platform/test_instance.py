import gevent
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_ip_and_port
from volttrontesting.fixtures.vc_fixtures import vc_instance
from volttron.platform.vip.agent.subsystems import query


# def test_can_get_multiple_addresses_from_query():
#     vip_addresses = ("tcp://{}".format(get_rand_ip_and_port()),
#                    "tcp://{}".format(get_rand_ip_and_port()))
#     wrapper = PlatformWrapper()
#     wrapper.startup_platform(vip_addresses)
#     agent = wrapper.build_agent()
#     q = query.Query(agent.core)
#
#     addresses == q.query(b'addresses').get(timeout=2)
#     for addr in vip_addresses:
#         assert addr in addresses


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
