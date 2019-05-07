import os

import gevent
import pytest

from vctestutils import APITester
from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.agent_additions import add_volttron_central, \
    add_volttron_central_platform
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform

from vc_fixtures import vc_and_vcp_together, vc_instance, vcp_instance


@pytest.fixture(scope="module")
def multi_messagebus_vc_vcp(volttron_multi_messagebus):
    vcp_instance, vc_instance = volttron_multi_messagebus

    vcp_uuid = add_volttron_central_platform(vcp_instance)
    vc_uuid = add_volttron_central(vc_instance)

    assert vcp_uuid
    assert vc_uuid



    yield vcp_instance, vc_instance

    vcp_instance.remove_agent(vcp_uuid)
    vc_instance.remove_agent(vc_uuid)


def test_able_to_register(multi_messagebus_vc_vcp):

    vcp_instance, vc_instance = multi_messagebus_vc_vcp


    print("foo")


#
#
# @pytest.mark.vc
# @pytest.fixture(params=[
#     ('vc-first', 'local'),
#     ('vc-first', 'http'),
#     ('vcp-first', 'local'),
#     ('vcp-first', 'http')
# ])
# def both_with_vc_vcp(request):
#     """
#     Adds the volttron-central-address and volttron-central-serverkey to the
#     main instance configuration file before starting the platform
#     """
#     p = PlatformWrapper()
#
#     if request.param[1] == 'local':
#         start_wrapper_platform(p, with_http=True, add_local_vc_address=True)
#     else:
#         start_wrapper_platform(p, with_http=True)
#
#     if request.param[0] == 'vcp-first':
#         vcp_uuid = add_volttron_central_platform(p)
#         vc_uuid = add_volttron_central(p)
#     else:
#         vc_uuid = add_volttron_central(p)
#         vcp_uuid = add_volttron_central_platform(p)
#
#     # Give the agents a chance to do stuff. note might take up to 10 sec
#     # if the vcp is started first.
#     gevent.sleep(10)
#     yield p
#
#     p.shutdown_platform()
#
#
# @pytest.mark.vc
# def test_autoregister_external(vc_vcp_platforms):
#
#     vc, vcp = vc_vcp_platforms
#
#     api = APITester(vc.jsonrpc_endpoint)
#
#     platforms = api.list_platforms()
#     assert len(platforms) == 1
#     p = platforms[0]
#     assert p['uuid']
#     assert p['name'] == vcp.vip_address
#     assert vcp.vip_address != vc.vip_address
#     assert isinstance(p['health'], dict)
#     assert STATUS_GOOD == p['health']['status']
#
#
# @pytest.mark.vc
# @pytest.mark.skipif(os.environ.get("CI") is not None,
#                     reason="Flaky on travis-ci for some reason")
# def test_autoregister_local(both_with_vc_vcp):
#
#     api = APITester(both_with_vc_vcp.jsonrpc_endpoint)
#
#     platforms = api.list_platforms()
#     assert len(platforms) == 1
#     p = platforms[0]
#     assert p['uuid']
#     assert p['name'] == both_with_vc_vcp.vip_address
#     assert isinstance(p['health'], dict)
#     assert STATUS_GOOD == p['health']['status']
#
